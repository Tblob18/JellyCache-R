"""SettingsService behaviour when media_server is jellyfin."""

import json
from unittest.mock import MagicMock

import pytest

from web.services import settings_service as ss_mod


class _FakeManager:
    server_name = "jf"
    server_version = "10.10.3"

    def get_libraries(self):
        return [
            {"id": "g1", "section_id": 11, "name": "Movies", "type": "movies", "locations": ["/data/movies/"]},
            {"id": "g2", "section_id": 22, "name": "Shows", "type": "tvshows", "locations": ["/data/tv/"]},
        ]

    def list_users(self):
        return [{"name": "kid", "id": "u2", "is_admin": False},
                {"name": "paul", "id": "u1", "is_admin": True}]


@pytest.fixture
def service(tmp_path, monkeypatch):
    settings_file = tmp_path / "plexcache_settings.json"
    settings_file.write_text(json.dumps({
        "media_server": "jellyfin", "JELLYFIN_URL": "http://jf:8096", "JELLYFIN_API_KEY": "k",
        "users": [{"title": "paul", "skip_ondeck": False, "skip_watchlist": True, "days_to_monitor": 3},
                  {"title": "gone", "skip_ondeck": False}],
    }))
    svc = ss_mod.SettingsService()
    monkeypatch.setattr(svc, "_load_raw", lambda: json.loads(settings_file.read_text()))
    monkeypatch.setattr(svc, "_save_raw", lambda raw: settings_file.write_text(json.dumps(raw)) or True)
    monkeypatch.setattr(ss_mod.SettingsService, "_jellyfin_manager", staticmethod(lambda url, key: _FakeManager()))
    svc._settings_file = settings_file
    return svc


def test_libraries_in_plex_shape(service):
    libs = service.get_plex_libraries()
    assert [(l["id"], l["title"], l["type"], l["type_label"]) for l in libs] == [
        (11, "Movies", "movie", "Movies"), (22, "Shows", "show", "TV Shows")]
    assert libs[0]["locations"] == ["/data/movies"]


def test_users_in_plex_shape_admin_first(service):
    users = service.get_plex_users()
    assert [u["title"] for u in users] == ["paul", "kid"]
    assert users[0]["is_admin"] and users[0]["is_home"]


def test_sync_preserves_preferences(service):
    result = service.sync_users_from_plex()
    assert result["success"] and result["added_count"] == 1 and result["removed_count"] == 1
    saved = json.loads(service._settings_file.read_text())
    paul = next(u for u in saved["users"] if u["title"] == "paul")
    assert paul["skip_watchlist"] is True and paul["days_to_monitor"] == 3 and paul["id"] == "u1"
    assert saved["skip_watchlist"] == ["paul"]


def test_connection_test_messages(service, monkeypatch):
    assert service.test_jellyfin_connection("http://jf", "k")["success"]
    monkeypatch.setattr(ss_mod.SettingsService, "_jellyfin_manager",
                        staticmethod(MagicMock(side_effect=Exception("401 Unauthorized"))))
    result = service.test_jellyfin_connection("http://jf", "bad")
    assert not result["success"] and "API key rejected" in result["message"]
    assert not service.test_jellyfin_connection("", "")["success"]


def test_save_switches_server(service):
    service.save_plex_settings({"media_server": "plex", "plex_url": "http://plex:32400", "plex_token": "t"})
    saved = json.loads(service._settings_file.read_text())
    assert saved["media_server"] == "plex" and saved["JELLYFIN_URL"] == "http://jf:8096"
    service.save_plex_settings({"media_server": "jellyfin", "jellyfin_url": " http://new:8096/ ",
                                "jellyfin_api_key": " k2 "})
    saved = json.loads(service._settings_file.read_text())
    assert (saved["media_server"], saved["JELLYFIN_URL"], saved["JELLYFIN_API_KEY"]) == \
        ("jellyfin", "http://new:8096", "k2")
