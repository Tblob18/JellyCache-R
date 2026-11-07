"""Tests for core/move_journal.py."""

import json
from datetime import datetime, timedelta

import pytest

from core import move_journal as mj


@pytest.fixture
def jfile(tmp_path, monkeypatch):
    monkeypatch.setattr(mj, "_retention_days", lambda: 30)
    return tmp_path / "move_journal.jsonl"


def _journal(jfile, run_id="r1", dry_run=False):
    return mj.MoveJournal(run_id, run_source="cli", dry_run=dry_run,
                          media_server="jellyfin", journal_file=jfile)


def test_record_finalize_and_load(jfile, tmp_path):
    f = tmp_path / "a.mkv"
    f.write_bytes(b"x" * 10)
    j = _journal(jfile)
    j.record("cache", str(f), "next_up", "Next Up for paul", users=["paul", "paul"],
             media={"type": "episode", "show": "Show"})
    j.record("restore", "/m/b.mkv", "movie_inactive", "gone", size_bytes=5)
    j.set_status("cache", str(f), mj.DONE)
    assert j.finalize() == 2
    assert j.finalize() == 0  # idempotent

    entries = mj.load_entries(jfile)
    by_action = {e["action"]: e for e in entries}
    assert by_action["cache"]["status"] == "done"
    assert by_action["cache"]["size_bytes"] == 10
    assert by_action["cache"]["users"] == ["paul"]
    # never confirmed on a real run -> failed
    assert by_action["restore"]["status"] == "failed"


def test_dry_run_entries_marked_dry_run(jfile):
    j = _journal(jfile, dry_run=True)
    j.record("cache", "/m/a.mkv", "favorite", "fav", size_bytes=1)
    j.finalize()
    assert mj.load_entries(jfile)[0]["status"] == "dry_run"


def test_discard_and_pending(jfile):
    j = _journal(jfile)
    j.record("cache", "/m/a.mkv", "favorite", "fav", size_bytes=1)
    j.record("cache", "/m/b.mkv", "favorite", "fav", size_bytes=1)
    assert sorted(j.pending("cache")) == ["/m/a.mkv", "/m/b.mkv"]
    assert j.discard("cache", "/m/a.mkv")["reason"] == "fav"
    assert j.pending("cache") == ["/m/b.mkv"]


def test_prune_drops_old_lines(jfile):
    old = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
    jfile.write_text(json.dumps({"ts": old, "run_id": "old", "action": "cache"}) + "\n")
    j = _journal(jfile)
    j.record("cache", "/m/a.mkv", "favorite", "fav", size_bytes=1)
    j.finalize()
    assert [e["run_id"] for e in mj.load_entries(jfile)] == ["r1"]


def test_filters_runs_and_stats(jfile):
    j1 = _journal(jfile, "r1")
    j1.record("cache", "/m/a.mkv", "next_up", "x", users=["paul"], size_bytes=100,
              media={"show": "Show"}, status=mj.DONE)
    j1.record("cache", "/m/b.mkv", "favorite", "x", users=["kid"], size_bytes=50, status=mj.DONE)
    j1.finalize()
    j2 = _journal(jfile, "r2")
    j2.record("restore", "/m/a.mkv", "episode_done", "x", size_bytes=100, status=mj.DONE)
    j2.record("cache", "/m/a.mkv", "next_up", "x", users=["paul"], size_bytes=100, status=mj.DONE)
    j2.finalize()
    jd = _journal(jfile, "r3", dry_run=True)
    jd.record("cache", "/m/z.mkv", "favorite", "x", size_bytes=999)
    jd.finalize()

    entries = mj.load_entries(jfile)
    assert len(mj.filter_entries(entries, action="cache")) == 4
    assert len(mj.filter_entries(entries, user="kid")) == 1
    assert len(mj.filter_entries(entries, query="b.mkv")) == 1
    assert len(mj.filter_entries(entries, include_dry_run=False)) == 4

    runs = mj.summarize_runs(entries)
    assert {r["run_id"] for r in runs} == {"r1", "r2", "r3"}

    stats = mj.compute_stats(entries, days=7)
    assert stats["runs"] == 2  # dry run excluded
    assert stats["cached_files"] == 3
    assert stats["restored_files"] == 1
    assert stats["bytes_cached"] == 250
    assert stats["per_day"][-1]["cache"] == 250
    assert stats["users"][0] == {"user": "paul", "bytes": 200}
    assert stats["shows"][0] == {"show": "Show", "count": 1}
    assert stats["churn"] == [{"path": "/m/a.mkv", "name": "a.mkv", "count": 2}]
    assert {r["code"] for r in stats["reasons"]} == {"next_up", "favorite", "episode_done"}
