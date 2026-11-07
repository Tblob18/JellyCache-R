"""What is playing right now, and is it being served from the cache?

Used by the web UI's Stats page. A play served from the cache means the array
disks holding that title can stay spun down - the whole point of the tool.
"""

import logging
import os
from typing import Any, Dict, List, Optional


def create_media_manager(config_manager, timeout: int = 10):
    """PlexManager or JellyfinManager for a loaded ConfigManager (connected)."""
    plex_cfg = config_manager.plex
    if getattr(plex_cfg, "media_server", "plex") == "jellyfin":
        from core.jellyfin_api import JellyfinManager
        manager = JellyfinManager(plex_cfg.jellyfin_url, plex_cfg.jellyfin_api_key,
                                  retry_limit=1, timeout=timeout)
    else:
        from core.plex_api import PlexManager
        manager = PlexManager(plex_cfg.plex_url, plex_cfg.plex_token, timeout=timeout)
    manager.connect()
    return manager


def _plex_session_info(session) -> Dict[str, Any]:
    path = None
    try:
        path = session.media[0].parts[0].file
    except (AttributeError, IndexError, TypeError):
        pass
    user = ""
    try:
        user = (session.usernames or [""])[0]
    except (AttributeError, TypeError):
        pass
    title = getattr(session, "title", "")
    if getattr(session, "type", "") == "episode":
        title = f"{getattr(session, 'grandparentTitle', '')} - {title}"
    return {"user": user, "title": title, "server_path": path,
            "client": getattr(getattr(session, "player", None), "title", "")}


def _jellyfin_session_info(manager, session: Dict[str, Any]) -> Dict[str, Any]:
    item = session.get("NowPlayingItem") or {}
    title = item.get("Name", "")
    if item.get("SeriesName"):
        title = f"{item['SeriesName']} - {title}"
    return {"user": session.get("UserName", ""), "title": title,
            "server_path": manager.get_session_media_path(session),
            "client": session.get("Client", "")}


def get_now_playing(config_manager) -> Dict[str, Any]:
    """{"sessions": [...], "error": str|None}.

    Each session: user, title, client, server_path, real_path, cache_path,
    location ("cache" | "array" | "unknown").
    """
    try:
        manager = create_media_manager(config_manager)
        sessions = manager.get_active_sessions() or []
    except Exception as e:
        logging.debug(f"[NOW PLAYING] {e}")
        return {"sessions": [], "error": str(e)}

    from core.file_operations import MultiPathModifier
    modifier = MultiPathModifier(mappings=config_manager.paths.path_mappings or [])

    result: List[Dict[str, Any]] = []
    is_jellyfin = getattr(config_manager.plex, "media_server", "plex") == "jellyfin"
    for session in sessions:
        try:
            info = (_jellyfin_session_info(manager, session) if is_jellyfin
                    else _plex_session_info(session))
        except Exception as e:
            logging.debug(f"[NOW PLAYING] Could not read session: {e}")
            continue
        info.update({"real_path": None, "cache_path": None, "location": "unknown"})
        server_path = info.get("server_path")
        if server_path:
            real = (modifier.modify_file_paths([server_path]) or [None])[0]
            info["real_path"] = real
            cache_path: Optional[str] = None
            if real:
                try:
                    cache_path, _ = modifier.convert_real_to_cache(real)
                except Exception:
                    cache_path = None
            info["cache_path"] = cache_path
            if cache_path and os.path.exists(cache_path):
                info["location"] = "cache"
            elif real:
                info["location"] = "array"
        result.append(info)
    return {"sessions": result, "error": None}
