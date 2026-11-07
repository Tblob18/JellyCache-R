"""Route tests for the Moves (journal) and Stats pages."""

import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

for _name in ["web.config", "web.routers", "web.services", "web"]:
    if isinstance(sys.modules.get(_name), MagicMock):
        del sys.modules[_name]

from core import move_journal as mj  # noqa: E402
import web.config  # noqa: E402,F401
from web.routers import insights  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    jfile = tmp_path / "move_journal.jsonl"
    monkeypatch.setattr(mj, "JOURNAL_FILE", jfile)
    monkeypatch.setattr(mj, "_retention_days", lambda: 30)
    monkeypatch.setattr(insights, "_cache_usage", lambda: None)

    real = mj.MoveJournal("run-real-1", run_source="scheduled", media_server="jellyfin", journal_file=jfile)
    real.record("cache", "/mnt/user/tv/Show/S01E03.mkv", "prefetch",
                "Upcoming episode after Show S01E02 (paul)", users=["paul"], size_bytes=2048,
                media={"type": "episode", "show": "Show", "season": 1, "episode": 3}, status=mj.DONE)
    real.record("restore", "/mnt/user/movies/Film.mkv", "movie_inactive",
                "Film is no longer on any user's Continue Watching or Favorites", size_bytes=4096,
                status=mj.DONE)
    real.record("cache", "/mnt/user/movies/Big.mkv", "favorite", "In kid's Favorites",
                users=["kid"], size_bytes=1, status=mj.FAILED, note="Not on cache after the move step")
    real.finalize()
    dry = mj.MoveJournal("run-dry-1", dry_run=True, journal_file=jfile)
    dry.record("cache", "/mnt/user/movies/Maybe.mkv", "favorite", "In paul's Favorites", size_bytes=10)
    dry.finalize()

    app = FastAPI()
    app.include_router(insights.router, prefix="/moves")
    app.include_router(insights.stats_router, prefix="/stats")
    return TestClient(app)


def test_moves_list_shows_reasons(client):
    html = client.get("/moves/list?days=7").text
    assert "Upcoming episode after Show S01E02 (paul)" in html
    assert "S01E03.mkv" in html
    assert "Maybe.mkv" in html  # dry runs shown by default
    assert "4 decisions" in html


def test_moves_list_filters(client):
    html = client.get("/moves/list?days=7&action=restore").text
    assert "Film.mkv" in html and "S01E03.mkv" not in html
    html = client.get("/moves/list?days=7&dry=hide").text
    assert "Maybe.mkv" not in html
    html = client.get("/moves/list?days=7&run_id=run-dry-1").text
    assert "1 decision " in html
    html = client.get("/moves/list?days=7&status=failed").text
    assert "Big.mkv" in html and "mv-row-failed" in html


def test_moves_page_prefills_filters(client):
    html = client.get("/moves?reason=favorite&status=failed").text
    assert '<option value="favorite" selected>' in html
    assert '<option value="failed" selected>' in html


def test_moves_export_csv(client):
    resp = client.get("/moves/export?days=7&dry=hide")
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("ts,run_id,run_source")
    assert len(lines) == 4


def test_stats_page(client):
    html = client.get("/stats?days=30").text
    assert "Upcoming episode" in html     # reason breakdown
    assert "paul" in html and "kid" not in html.split("Cached per user")[1].split("Top shows")[0]
    assert "Recent failures" in html
    assert "Maybe.mkv" not in html        # dry run excluded


def test_stats_now_playing_handles_unreachable_server(client, monkeypatch):
    import core.now_playing as np
    monkeypatch.setattr(np, "create_media_manager", MagicMock(side_effect=ConnectionError("refused")))
    import core.config as cfgmod
    monkeypatch.setattr(cfgmod.ConfigManager, "load_config", lambda self, persist_updates=True: None)
    html = client.get("/stats/now").text
    assert "Could not reach the media server" in html
