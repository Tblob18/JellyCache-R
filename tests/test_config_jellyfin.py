"""ConfigManager handling of media_server = "jellyfin"."""

import json
import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault('fcntl', MagicMock())
sys.modules.setdefault('plexapi', MagicMock())
sys.modules.setdefault('plexapi.server', MagicMock())

from core.config import ConfigManager
from tests.test_config_read_only_load import _minimal_settings


def _write(tmp_path, data):
    path = tmp_path / "plexcache_settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _jellyfin_settings(tmp_path):
    data = _minimal_settings(tmp_path)
    del data["PLEX_URL"], data["PLEX_TOKEN"]
    data.update({
        "media_server": "Jellyfin",
        "JELLYFIN_URL": "http://jellyfin:8096",
        "JELLYFIN_API_KEY": "abc123",
        "valid_sections": ["Movies"],
    })
    return data


def test_jellyfin_config_loads_without_plex_credentials(tmp_path):
    cfg = ConfigManager(str(_write(tmp_path, _jellyfin_settings(tmp_path))))
    cfg.load_config(persist_updates=False)
    assert cfg.plex.media_server == "jellyfin"
    assert cfg.plex.jellyfin_url == "http://jellyfin:8096"
    assert cfg.plex.jellyfin_api_key == "abc123"
    assert cfg.plex.valid_sections == ["Movies"]


@pytest.mark.parametrize("missing", ["JELLYFIN_URL", "JELLYFIN_API_KEY"])
def test_jellyfin_config_requires_credentials(tmp_path, missing):
    data = _jellyfin_settings(tmp_path)
    del data[missing]
    cfg = ConfigManager(str(_write(tmp_path, data)))
    with pytest.raises(ValueError, match=missing):
        cfg.load_config(persist_updates=False)


def test_jellyfin_empty_api_key_rejected(tmp_path):
    data = _jellyfin_settings(tmp_path)
    data["JELLYFIN_API_KEY"] = " "
    cfg = ConfigManager(str(_write(tmp_path, data)))
    with pytest.raises(ValueError, match="JELLYFIN_API_KEY"):
        cfg.load_config(persist_updates=False)


def test_unknown_media_server_rejected(tmp_path):
    data = _minimal_settings(tmp_path)
    data["media_server"] = "emby"
    cfg = ConfigManager(str(_write(tmp_path, data)))
    with pytest.raises(ValueError, match="media_server"):
        cfg.load_config(persist_updates=False)


def test_plex_remains_default_and_requires_token(tmp_path):
    data = _minimal_settings(tmp_path)
    cfg = ConfigManager(str(_write(tmp_path, data)))
    cfg.load_config(persist_updates=False)
    assert cfg.plex.media_server == "plex"

    del data["PLEX_TOKEN"]
    cfg = ConfigManager(str(_write(tmp_path, data)))
    with pytest.raises(ValueError, match="PLEX_TOKEN"):
        cfg.load_config(persist_updates=False)
