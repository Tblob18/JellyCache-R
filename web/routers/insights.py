"""Moves (journal) and Stats pages.

* ``GET /moves``          - page: every move decision with its reason
* ``GET /moves/list``     - HTMX partial: filtered journal table
* ``GET /moves/export``   - CSV download of the filtered journal
* ``GET /stats``          - page: aggregates over the journal + cache usage
* ``GET /stats/now``      - HTMX partial: what is playing, cache vs array
"""

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from core import move_journal as mj
from core.system_utils import format_bytes
from web.config import SETTINGS_FILE, templates

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_DAYS = (1, 7, 30, 90)
PAGE_SIZE = 300

ACTION_LABELS = {
    "cache": "Cached",
    "restore": "Moved back",
    "evict": "Evicted",
    "release": "Released",
    "skip": "Skipped",
    "hold": "Held",
}
STATUS_LABELS = {
    "done": "Done",
    "failed": "Failed",
    "dry_run": "Dry run",
    "held": "Held",
    "skipped": "Skipped",
    "planned": "Planned",
}


def _days(value: int) -> int:
    return value if value in ALLOWED_DAYS else 7


def _filtered(days: int, run_id: str, action: str, reason: str, status: str, user: str,
              q: str, dry: str):
    entries = mj.load_entries(days=_days(days), run_id=run_id or None)
    return entries, mj.filter_entries(
        entries, action=action, reason=reason, status=status, user=user, query=q,
        include_dry_run=(dry != "hide"),
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
def moves_page(request: Request, run_id: str = "", days: int = 7, action: str = "",
               reason: str = "", status: str = "", q: str = ""):
    return templates.TemplateResponse(request, "insights/moves.html", {
        "page_title": "Moves",
        "run_id": run_id,
        "pre": {"days": _days(days), "action": action, "reason": reason, "status": status, "q": q},
        "allowed_days": ALLOWED_DAYS,
        "action_labels": ACTION_LABELS,
        "status_labels": STATUS_LABELS,
        "reason_labels": mj.REASON_LABELS,
    })


@router.get("/list", response_class=HTMLResponse)
def moves_list(request: Request, days: int = 7, run_id: str = "", action: str = "",
               reason: str = "", status: str = "", user: str = "", q: str = "",
               dry: str = "show"):
    all_entries, entries = _filtered(days, run_id, action, reason, status, user, q, dry)
    runs = mj.summarize_runs(all_entries)[:30]
    users = sorted({u for e in all_entries for u in (e.get("users") or [])}, key=str.lower)
    reasons_present = sorted({e.get("reason_code", "") for e in all_entries})
    total_bytes = sum(e.get("size_bytes", 0) for e in entries)
    return templates.TemplateResponse(request, "insights/partials/moves_list.html", {
        "entries": entries[:PAGE_SIZE],
        "total": len(entries),
        "truncated": len(entries) > PAGE_SIZE,
        "total_size": format_bytes(total_bytes) if total_bytes else "0 B",
        "runs": runs,
        "users": users,
        "reasons_present": reasons_present,
        "action_labels": ACTION_LABELS,
        "status_labels": STATUS_LABELS,
        "reason_labels": mj.REASON_LABELS,
        "format_bytes": format_bytes,
        "f": {"days": _days(days), "run_id": run_id, "action": action, "reason": reason,
              "status": status, "user": user, "q": q, "dry": dry},
    })


@router.get("/export")
def moves_export(days: int = 7, run_id: str = "", action: str = "", reason: str = "",
                 status: str = "", user: str = "", q: str = "", dry: str = "show"):
    _, entries = _filtered(days, run_id, action, reason, status, user, q, dry)
    buf = io.StringIO()
    writer = csv.writer(buf)
    cols = ["ts", "run_id", "run_source", "dry_run", "server", "action", "status",
            "reason_code", "reason", "users", "size_bytes", "path", "related", "note"]
    writer.writerow(cols)
    for e in entries:
        row = dict(e, users=";".join(e.get("users") or []))
        writer.writerow([row.get(c, "") for c in cols])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=plexcache_moves.csv"},
    )


# ------------------------------------------------------------------ stats

stats_router = APIRouter()


def _cache_usage() -> Optional[dict]:
    try:
        from web.services import get_cache_service
        stats = get_cache_service().get_cache_stats()
        return stats if isinstance(stats, dict) else None
    except Exception as e:
        logger.debug(f"Stats: cache usage unavailable: {e}")
        return None


@stats_router.get("", response_class=HTMLResponse, include_in_schema=False)
@stats_router.get("/", response_class=HTMLResponse)
def stats_page(request: Request, days: int = 30):
    days = _days(days) if days != 30 else 30
    entries = mj.load_entries(days=days)
    stats = mj.compute_stats(entries, days=days)
    peak = max([max(d["cache"], d["restore"], d["evict"]) for d in stats["per_day"]] or [0]) or 1
    max_user = max([u["bytes"] for u in stats["users"]] or [0]) or 1
    max_reason = max([r["count"] for r in stats["reasons"]] or [0]) or 1
    runs = mj.summarize_runs([e for e in entries if not e.get("dry_run")])
    return templates.TemplateResponse(request, "insights/stats.html", {
        "page_title": "Stats",
        "s": stats,
        "days": days,
        "allowed_days": ALLOWED_DAYS,
        "peak": peak,
        "max_user": max_user,
        "max_reason": max_reason,
        "last_run": runs[0] if runs else None,
        "cache": _cache_usage(),
        "format_bytes": format_bytes,
        "reason_labels": mj.REASON_LABELS,
    })


@stats_router.get("/now", response_class=HTMLResponse)
def stats_now_playing(request: Request):
    from core.config import ConfigManager
    from core.now_playing import get_now_playing
    try:
        cfg = ConfigManager(str(SETTINGS_FILE))
        cfg.load_config(persist_updates=False)
        data = get_now_playing(cfg)
    except Exception as e:
        data = {"sessions": [], "error": str(e)}
    return templates.TemplateResponse(request, "insights/partials/now_playing.html", data)
