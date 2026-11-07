"""Move journal: what PlexCache moved during a run, and *why*.

The activity feed (core/activity.py) answers "what happened recently" with a
filename and an action. The journal is the audit trail behind it: one record
per decision, with the full path, the reason code, a human-readable reason,
the users that caused it and the final outcome. It is written by core/app.py
for every run (CLI, web, scheduled — and dry runs, which is what makes it
useful for testing settings), and read by the web UI's Moves and Stats pages.

Storage: ``data/move_journal.jsonl``, one JSON object per line, pruned to
``move_journal_retention_days`` (default 30) whenever a run is appended.
"""

import json
import logging
import os
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.activity import DATA_DIR, SETTINGS_FILE

JOURNAL_FILE = DATA_DIR / "move_journal.jsonl"
DEFAULT_RETENTION_DAYS = 30
MAX_ENTRIES_PER_RUN = 20000

# Actions
CACHE, RESTORE, EVICT, RELEASE, SKIP, HOLD = "cache", "restore", "evict", "release", "skip", "hold"
ACTIONS = (CACHE, RESTORE, EVICT, RELEASE, SKIP, HOLD)

# Statuses
PLANNED, DONE, FAILED, DRY_RUN, HELD, SKIPPED = "planned", "done", "failed", "dry_run", "held", "skipped"

# Reason code -> short label (UI filter chips, stats legend)
REASON_LABELS: Dict[str, str] = {
    "continue_watching": "Continue Watching",
    "on_deck": "On Deck",
    "next_up": "Next Up",
    "prefetch": "Upcoming episode",
    "favorite": "Favorite",
    "watchlist": "Watchlist",
    "pinned": "Pinned",
    "sidecar": "Sidecar file",
    "below_priority": "Priority too low",
    "not_moved": "Not moved",
    "episode_done": "Episode watched / outside window",
    "show_inactive": "Show no longer active",
    "movie_inactive": "Movie no longer active",
    "retention_hold": "Retention hold",
    "active_session": "Currently playing",
    "hardlinked": "Hard-linked",
    "evicted_priority": "Evicted (priority)",
    "evicted_fifo": "Evicted (oldest)",
    "released": "Released to mover",
    "unknown": "Unknown",
}

_write_lock = threading.Lock()


def _retention_days() -> int:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            value = json.load(f).get("move_journal_retention_days", DEFAULT_RETENTION_DAYS)
        return max(1, int(value))
    except (OSError, ValueError, TypeError, AttributeError):
        return DEFAULT_RETENTION_DAYS


class MoveJournal:
    """Collects decisions for one run and appends them to the journal file."""

    def __init__(self, run_id: str, run_source: str = "cli", dry_run: bool = False,
                 media_server: str = "plex", journal_file: Optional[Path] = None):
        self.run_id = run_id
        self.run_source = run_source
        self.dry_run = dry_run
        self.media_server = media_server
        self.journal_file = Path(journal_file) if journal_file else JOURNAL_FILE
        self.started_at = datetime.now()
        self._entries: Dict[tuple, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._finalized = False

    # ------------------------------------------------------------- recording

    def record(self, action: str, path: str, reason_code: str, reason: str, *,
               users: Optional[Iterable[str]] = None, size_bytes: Optional[int] = None,
               media: Optional[Dict[str, Any]] = None, related: Optional[str] = None,
               status: str = PLANNED, **extra: Any) -> None:
        """Record (or overwrite) the decision for ``path`` under ``action``."""
        if not path:
            return
        if size_bytes is None:
            try:
                size_bytes = os.path.getsize(path)
            except OSError:
                size_bytes = 0
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "run_id": self.run_id,
            "run_source": self.run_source,
            "dry_run": self.dry_run,
            "server": self.media_server,
            "action": action,
            "status": status,
            "path": path,
            "name": os.path.basename(path),
            "reason_code": reason_code,
            "reason": reason,
            "users": sorted(set(users or [])),
            "size_bytes": int(size_bytes or 0),
        }
        if media:
            entry["media"] = media
        if related:
            entry["related"] = related
        entry.update({k: v for k, v in extra.items() if v is not None})
        with self._lock:
            if len(self._entries) < MAX_ENTRIES_PER_RUN or (action, path) in self._entries:
                self._entries[(action, path)] = entry

    def set_status(self, action: str, path: str, status: str, note: Optional[str] = None) -> None:
        with self._lock:
            entry = self._entries.get((action, path))
            if entry is not None:
                entry["status"] = status
                if note:
                    entry["note"] = note

    def discard(self, action: str, path: str) -> Optional[Dict[str, Any]]:
        """Remove and return the entry for (action, path), if any."""
        with self._lock:
            return self._entries.pop((action, path), None)

    def pending(self, action: str) -> List[str]:
        with self._lock:
            return [p for (a, p), e in self._entries.items() if a == action and e["status"] == PLANNED]

    def entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries.values())

    # -------------------------------------------------------------- persist

    def finalize(self) -> int:
        """Append this run's entries to the journal and prune old lines.

        Entries still ``planned`` are marked ``dry_run`` on a dry run and
        ``failed`` otherwise (the run ended before confirming them).
        Returns the number of entries written.
        """
        if self._finalized:
            return 0
        self._finalized = True
        entries = self.entries()
        for e in entries:
            if e["status"] == PLANNED:
                e["status"] = DRY_RUN if self.dry_run else FAILED
        if not entries:
            return 0
        try:
            self.journal_file.parent.mkdir(parents=True, exist_ok=True)
            with _write_lock:
                _prune(self.journal_file, _retention_days())
                with open(self.journal_file, "a", encoding="utf-8") as f:
                    for e in entries:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except OSError as e:
            logging.warning(f"[JOURNAL] Could not write move journal: {e}")
            return 0
        logging.debug(f"[JOURNAL] Recorded {len(entries)} decisions for run {self.run_id}")
        return len(entries)


def _prune(journal_file: Path, retention_days: int) -> None:
    """Drop lines older than the retention window (rewrite only when needed)."""
    if not journal_file.exists():
        return
    cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat(timespec="seconds")
    try:
        with open(journal_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return
    kept = [ln for ln in lines if _line_ts(ln) >= cutoff]
    if len(kept) == len(lines):
        return
    tmp = journal_file.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(kept)
    os.replace(tmp, journal_file)


def _line_ts(line: str) -> str:
    # "ts" is always the first key; avoid a full json parse for pruning.
    start = line.find('"ts": "')
    return line[start + 7:start + 26] if start >= 0 else ""


# ---------------------------------------------------------------- reading

def load_entries(journal_file: Optional[Path] = None, days: Optional[int] = None,
                 run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Journal entries, newest first."""
    path = Path(journal_file) if journal_file else JOURNAL_FILE
    if not path.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds") if days else ""
    result = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if cutoff and _line_ts(line) < cutoff:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if run_id and entry.get("run_id") != run_id:
                    continue
                result.append(entry)
    except OSError as e:
        logging.warning(f"[JOURNAL] Could not read move journal: {e}")
        return []
    result.reverse()
    return result


def filter_entries(entries: List[Dict[str, Any]], action: str = "", reason: str = "",
                   status: str = "", user: str = "", query: str = "",
                   include_dry_run: bool = True) -> List[Dict[str, Any]]:
    q = query.lower().strip()
    out = []
    for e in entries:
        if action and e.get("action") != action:
            continue
        if reason and e.get("reason_code") != reason:
            continue
        if status and e.get("status") != status:
            continue
        if user and user not in (e.get("users") or []):
            continue
        if not include_dry_run and e.get("dry_run"):
            continue
        if q and q not in e.get("path", "").lower() and q not in e.get("reason", "").lower():
            continue
        out.append(e)
    return out


def summarize_runs(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One summary row per run (newest first)."""
    runs: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        rid = e.get("run_id") or "?"
        run = runs.get(rid)
        if run is None:
            run = runs[rid] = {
                "run_id": rid, "ts": e.get("ts", ""), "run_source": e.get("run_source", ""),
                "dry_run": e.get("dry_run", False), "server": e.get("server", ""),
                "counts": Counter(), "bytes": Counter(), "failed": 0,
            }
        run["ts"] = max(run["ts"], e.get("ts", ""))
        key = e.get("action", "")
        run["counts"][key] += 1
        if e.get("status") in (DONE, DRY_RUN):
            run["bytes"][key] += e.get("size_bytes", 0)
        if e.get("status") == FAILED:
            run["failed"] += 1
    return sorted(runs.values(), key=lambda r: r["ts"], reverse=True)


def compute_stats(entries: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
    """Aggregate real (non dry-run) journal entries for the Stats page."""
    real = [e for e in entries if not e.get("dry_run")]
    today = datetime.now().date()
    day_keys = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    per_day = {d: {"cache": 0, "restore": 0, "evict": 0} for d in day_keys}

    totals = Counter()
    bytes_totals = Counter()
    reasons = Counter()
    users = Counter()
    shows = Counter()
    failures = []
    run_ids = set()

    for e in real:
        run_ids.add(e.get("run_id"))
        action, status = e.get("action"), e.get("status")
        totals[f"{action}:{status}"] += 1
        if status != DONE:
            if status == FAILED:
                failures.append(e)
            continue
        size = e.get("size_bytes", 0)
        bytes_totals[action] += size
        day = (e.get("ts") or "")[:10]
        bucket = "evict" if action in (EVICT, RELEASE) else action
        if day in per_day and bucket in per_day[day]:
            per_day[day][bucket] += size
        if action == CACHE:
            reasons[e.get("reason_code", "unknown")] += 1
            for u in e.get("users") or []:
                users[u] += size
            show = (e.get("media") or {}).get("show")
            if show:
                shows[show] += 1
        elif action in (RESTORE, EVICT):
            reasons[e.get("reason_code", "unknown")] += 1

    # Thrash detection: files cached and moved back more than once in the window.
    cycles = defaultdict(int)
    for e in real:
        if e.get("action") == CACHE and e.get("status") == DONE:
            cycles[e.get("path")] += 1
    churn = sorted(((p, n) for p, n in cycles.items() if n > 1), key=lambda x: -x[1])[:10]

    return {
        "days": days,
        "runs": len(run_ids),
        "cached_files": totals[f"{CACHE}:{DONE}"],
        "restored_files": totals[f"{RESTORE}:{DONE}"],
        "evicted_files": totals[f"{EVICT}:{DONE}"] + totals[f"{RELEASE}:{DONE}"],
        "skipped_files": totals[f"{SKIP}:{SKIPPED}"],
        "failed_files": len(failures),
        "bytes_cached": bytes_totals[CACHE],
        "bytes_restored": bytes_totals[RESTORE],
        "bytes_evicted": bytes_totals[EVICT] + bytes_totals[RELEASE],
        "per_day": [{"day": d, **per_day[d]} for d in day_keys],
        "reasons": [{"code": c, "label": REASON_LABELS.get(c, c), "count": n}
                    for c, n in reasons.most_common()],
        "users": [{"user": u, "bytes": b} for u, b in users.most_common(10)],
        "shows": [{"show": s, "count": n} for s, n in shows.most_common(10)],
        "churn": [{"path": p, "name": os.path.basename(p), "count": n} for p, n in churn],
        "recent_failures": failures[:10],
    }
