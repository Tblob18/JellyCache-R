"""
Jellyfin API integration for PlexCache-D.

Drop-in replacement for :class:`core.plex_api.PlexManager` when
``media_server`` is set to ``"jellyfin"``. It implements the subset of the
PlexManager interface the run loop (core/app.py) relies on:

    connect, load_user_tokens, get_newly_discovered_users, get_active_sessions,
    get_session_media_path, get_on_deck_media, get_watchlist_media,
    is_ondeck_data_complete, is_watchlist_data_complete, mark_watchlist_incomplete

Concept mapping:
    Plex OnDeck    -> Jellyfin "Continue Watching" (Resume) + "Next Up"
    Plex Watchlist -> Jellyfin Favorites (movies, series, episodes)
    Plex token     -> one admin API key (sees every user's data; no per-user tokens)
    Library section id -> Jellyfin library ItemId *or* library name
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests

from core.plex_api import OnDeckItem

# RunTimeTicks are 100ns units.
TICKS_PER_MINUTE = 10_000_000 * 60

ITEM_FIELDS = "Path,MediaSources,RunTimeTicks,ParentId"

WatchlistTuple = Tuple[str, str, Optional[datetime], Optional[Dict[str, Any]], Optional[str], str]


def _log_api_error(context: str, error: Exception) -> None:
    """Log API errors with hints for common HTTP status codes."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 401:
        logging.error(f"[JELLYFIN API] Authentication failed ({context}). "
                      f"Check JELLYFIN_API_KEY (Dashboard -> API Keys).")
    elif status == 403:
        logging.error(f"[JELLYFIN API] Access forbidden ({context}): {error}")
    elif status == 404:
        logging.warning(f"[JELLYFIN API] Not found ({context}): {error}")
    elif status is not None and status >= 500:
        logging.error(f"[JELLYFIN API] Server error ({context}): {error}")
    else:
        logging.error(f"[JELLYFIN API] Error ({context}): {type(error).__name__}: {error}")


def _parse_jellyfin_date(value: Optional[str]) -> Optional[datetime]:
    """Parse a Jellyfin ISO-8601 timestamp into an aware UTC datetime.

    Jellyfin emits 7 fractional digits (e.g. 2026-11-01T20:15:03.1234567Z),
    which ``datetime.fromisoformat`` rejects before Python 3.11.
    """
    if not value:
        return None
    try:
        text = value.strip().replace("Z", "+00:00")
        if "." in text:
            head, rest = text.split(".", 1)
            frac = ""
            i = 0
            while i < len(rest) and rest[i].isdigit():
                frac += rest[i]
                i += 1
            text = f"{head}.{frac[:6].ljust(6, '0')}{rest[i:]}"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        logging.debug(f"[JELLYFIN API] Could not parse date '{value}'")
        return None


def _item_path(item: Dict[str, Any]) -> Optional[str]:
    """Return the on-disk path of a Jellyfin item (primary version)."""
    path = item.get("Path")
    if path:
        return path
    for source in item.get("MediaSources") or []:
        if source.get("Path"):
            return source["Path"]
    return None


def _episode_info(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    season = item.get("ParentIndexNumber")
    episode = item.get("IndexNumber")
    if season is None or episode is None:
        return None
    return {"show": item.get("SeriesName", ""), "season": season, "episode": episode}


def _runtime_minutes(item: Dict[str, Any]) -> float:
    return (item.get("RunTimeTicks") or 0) / TICKS_PER_MINUTE


class JellyfinManager:
    """Manages Jellyfin server connections and media lookups."""

    def __init__(self, jellyfin_url: str, api_key: str, retry_limit: int = 3, delay: int = 5,
                 timeout: Optional[int] = None, watchlist_enabled: bool = True,
                 settings_users: Optional[List[dict]] = None):
        self.jellyfin_url = (jellyfin_url or "").rstrip("/")
        self.api_key = api_key
        self.retry_limit = max(1, retry_limit)
        self.delay = delay
        self.timeout = timeout or 30
        self.watchlist_enabled = watchlist_enabled
        # PlexManager exposes the plexapi server here; nothing Plex-specific works
        # with Jellyfin, so callers must check for None.
        self.plex = None
        self.server_name = ""
        self.server_version = ""

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f'MediaBrowser Token="{api_key}", Client="PlexCache-D", '
                             f'Device="PlexCache-D", DeviceId="plexcache-d", Version="1"',
            "X-Emby-Token": api_key,
            "Accept": "application/json",
        })

        self._users: Dict[str, str] = {}  # username -> user id
        self._admin_user: Optional[str] = None
        self._settings_users = settings_users or []
        self._newly_discovered_users: List[dict] = []
        self._users_loaded = False

        # library id / lowercase name -> list of folder locations
        self._libraries: Dict[str, Dict[str, Any]] = {}

        self._ondeck_data_complete = True
        self._watchlist_data_complete = True

    # ------------------------------------------------------------------ HTTP

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET a Jellyfin endpoint with retries on connection errors / 5xx."""
        url = f"{self.jellyfin_url}{endpoint}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_limit + 1):
            try:
                response = self._session.get(url, params=params, timeout=self.timeout)
                if response.status_code >= 500 and attempt < self.retry_limit:
                    raise requests.HTTPError(f"{response.status_code} Server Error", response=response)
                response.raise_for_status()
                return response.json() if response.content else {}
            except requests.HTTPError as e:
                last_error = e
                status = getattr(e.response, "status_code", 0) or 0
                if status < 500 or attempt >= self.retry_limit:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                if attempt >= self.retry_limit:
                    raise
            logging.debug(f"[JELLYFIN API] {endpoint} failed (attempt {attempt}), retrying in {self.delay}s")
            threading.Event().wait(self.delay)
        raise last_error  # pragma: no cover - loop always returns or raises

    # ------------------------------------------------------------- lifecycle

    def connect(self) -> None:
        """Verify the server is reachable and the API key works."""
        logging.debug(f"Connecting to Jellyfin server: {self.jellyfin_url}")
        if not self.jellyfin_url:
            raise ConnectionError("JELLYFIN_URL is not set")
        try:
            info = self._get("/System/Info")
        except Exception as e:
            _log_api_error("connect", e)
            raise ConnectionError(f"Cannot connect to Jellyfin server at {self.jellyfin_url}: {e}") from e
        self.server_name = info.get("ServerName", "")
        self.server_version = info.get("Version", "")
        logging.debug(f"Jellyfin server: {self.server_name} (version {self.server_version})")
        self._load_libraries()

    def _load_libraries(self) -> None:
        try:
            folders = self._get("/Library/VirtualFolders") or []
        except Exception as e:
            _log_api_error("list libraries", e)
            return
        for folder in folders:
            entry = {
                "id": folder.get("ItemId", ""),
                "name": folder.get("Name", ""),
                "type": folder.get("CollectionType", ""),
                "locations": [loc.rstrip("/") + "/" for loc in folder.get("Locations") or []],
            }
            if entry["id"]:
                self._libraries[entry["id"]] = entry
            if entry["name"]:
                self._libraries[entry["name"].lower()] = entry
        logging.debug(f"[JELLYFIN API] Libraries: "
                      f"{sorted({e['name'] for e in self._libraries.values()})}")

    def get_libraries(self) -> List[Dict[str, Any]]:
        """Return unique library entries (id, name, type, locations)."""
        seen, result = set(), []
        for entry in self._libraries.values():
            if entry["id"] not in seen:
                seen.add(entry["id"])
                result.append(entry)
        return result

    def _allowed_locations(self, valid_sections: Optional[List[Any]]) -> Optional[List[str]]:
        """Folder prefixes for the selected libraries, or None for 'all libraries'."""
        if not valid_sections:
            return None
        locations: List[str] = []
        for section in valid_sections:
            key = str(section)
            entry = self._libraries.get(key) or self._libraries.get(key.lower())
            if entry:
                locations.extend(entry["locations"])
            else:
                logging.warning(f"[JELLYFIN API] valid_sections entry '{section}' does not match any "
                                f"Jellyfin library id or name - ignoring it")
        if not locations:
            logging.warning("[JELLYFIN API] No valid_sections matched a library; using all libraries")
            return None
        return locations

    @staticmethod
    def _in_libraries(path: str, locations: Optional[List[str]]) -> bool:
        return locations is None or any(path.startswith(loc) for loc in locations)

    # ----------------------------------------------------------------- users

    def load_user_tokens(self, skip_users: Optional[List[str]] = None,
                         settings_users: Optional[List[dict]] = None,
                         main_username: Optional[str] = None) -> Dict[str, str]:
        """Load Jellyfin users. Returns username -> user id.

        The API key can read every user's data, so there are no per-user tokens.
        Users present on the server but missing from settings are reported via
        :meth:`get_newly_discovered_users` so the app can add them.
        """
        if self._users_loaded:
            return dict(self._users)
        if settings_users is not None:
            self._settings_users = settings_users
        known = {u.get("title") for u in self._settings_users if u.get("title")}
        try:
            users = self._get("/Users") or []
        except Exception as e:
            _log_api_error("list users", e)
            self._ondeck_data_complete = False
            self._watchlist_data_complete = False
            return {}

        for user in users:
            name, user_id = user.get("Name"), user.get("Id")
            if not name or not user_id:
                continue
            if (user.get("Policy") or {}).get("IsDisabled"):
                logging.debug(f"[USER:{name}] Disabled in Jellyfin, ignoring")
                continue
            self._users[name] = user_id
            if (user.get("Policy") or {}).get("IsAdministrator") and self._admin_user is None:
                self._admin_user = name
            if name not in known:
                self._newly_discovered_users.append({
                    "title": name,
                    "id": user_id,
                    "is_local": True,
                    "is_admin": bool((user.get("Policy") or {}).get("IsAdministrator")),
                    "skip_ondeck": False,
                    "skip_watchlist": False,
                })

        self._users_loaded = True
        logging.info(f"Connected to Jellyfin {self.server_name} ({len(self._users)} users)")
        if self._users:
            logging.info(f"USERS: {', '.join(sorted(self._users, key=str.lower))}")
        return dict(self._users)

    def get_newly_discovered_users(self) -> List[dict]:
        return self._newly_discovered_users

    def _users_for(self, users_toggle: bool, skip: List[str]) -> List[Tuple[str, str]]:
        if not self._users_loaded:
            self.load_user_tokens()
        skip_set = set(skip or [])
        if users_toggle:
            names = list(self._users)
        else:
            # Single-user mode: the first administrator (Plex's "main account").
            names = [self._admin_user] if self._admin_user else list(self._users)[:1]
        result = []
        for name in names:
            if name in skip_set:
                logging.info(f"[USER:{name}] Skipping - in skip list")
                continue
            result.append((name, self._users[name]))
        return result

    # --------------------------------------------------------------- status

    def is_ondeck_data_complete(self) -> bool:
        return self._ondeck_data_complete

    def is_watchlist_data_complete(self) -> bool:
        return self._watchlist_data_complete

    def mark_watchlist_incomplete(self) -> None:
        self._watchlist_data_complete = False

    def is_plex_tv_reachable(self) -> bool:
        return True

    # -------------------------------------------------------------- sessions

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Sessions that are currently playing something."""
        try:
            sessions = self._get("/Sessions", {"ActiveWithinSeconds": 960}) or []
        except Exception as e:
            _log_api_error("get sessions", e)
            return []
        return [s for s in sessions if s.get("NowPlayingItem")]

    def get_session_media_path(self, session: Dict[str, Any]) -> Optional[str]:
        """File path of the item playing in a session."""
        item = session.get("NowPlayingItem") or {}
        path = _item_path(item)
        if path:
            return path
        item_id, user_id = item.get("Id"), session.get("UserId")
        if not item_id or not user_id:
            return None
        try:
            full = self._get(f"/Users/{user_id}/Items/{item_id}")
            return _item_path(full)
        except Exception as e:
            _log_api_error(f"look up session item {item_id}", e)
            return None

    # --------------------------------------------------------------- on deck

    def get_on_deck_media(self, valid_sections: List[Any], days_to_monitor: int,
                          number_episodes: int, users_toggle: bool, skip_ondeck: List[str],
                          per_user_days: Optional[Dict[str, int]] = None,
                          prefetch_minimum_minutes: int = 0) -> List[OnDeckItem]:
        """Continue Watching + Next Up for every tracked user, plus upcoming episodes."""
        locations = self._allowed_locations(valid_sections)
        users = self._users_for(users_toggle, skip_ondeck)
        per_user_days = per_user_days or {}
        results: List[OnDeckItem] = []

        with ThreadPoolExecutor(max_workers=min(8, max(1, len(users)))) as pool:
            futures = {
                pool.submit(self._fetch_user_on_deck, name, uid,
                            per_user_days.get(name, days_to_monitor),
                            number_episodes, prefetch_minimum_minutes, locations): name
                for name, uid in users
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    items = future.result()
                except Exception as e:
                    _log_api_error(f"fetch Continue Watching for {name}", e)
                    self._ondeck_data_complete = False
                    continue
                logging.debug(f"[USER:{name}] Found {len(items)} OnDeck items")
                results.extend(items)
        return results

    def _fetch_user_on_deck(self, username: str, user_id: str, days: int, number_episodes: int,
                            prefetch_minimum_minutes: int,
                            locations: Optional[List[str]]) -> List[OnDeckItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days > 0 else None
        items: List[OnDeckItem] = []
        seen_paths = set()

        def add(item: Dict[str, Any], current: bool) -> bool:
            path = _item_path(item)
            if not path or path in seen_paths or not self._in_libraries(path, locations):
                return False
            seen_paths.add(path)
            items.append(OnDeckItem(
                file_path=path, username=username,
                episode_info=_episode_info(item) if item.get("Type") == "Episode" else None,
                is_current_ondeck=current, rating_key=item.get("Id"),
            ))
            logging.debug(f"[USER:{username}] OnDeck{'' if current else ' (prefetch)'}: {path}")
            return True

        # 1) Partially watched movies/episodes.
        resume = self._get(f"/Users/{user_id}/Items/Resume", {
            "Limit": 100, "Fields": ITEM_FIELDS, "MediaTypes": "Video",
            "EnableUserData": "true", "EnableImages": "false",
        }).get("Items", [])
        # 2) Next unwatched episode of shows in progress.
        next_up_params = {
            "UserId": user_id, "Limit": 100, "Fields": ITEM_FIELDS,
            "EnableUserData": "true", "EnableImages": "false", "EnableRewatching": "false",
        }
        if cutoff:
            next_up_params["NextUpDateCutoff"] = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        next_up = self._get("/Shows/NextUp", next_up_params).get("Items", [])

        handled_series = set()
        for item in resume + next_up:
            if item.get("Type") not in ("Movie", "Episode"):
                continue
            last_played = _parse_jellyfin_date((item.get("UserData") or {}).get("LastPlayedDate"))
            if cutoff and last_played and last_played < cutoff:
                logging.debug(f"[USER:{username}] Skipping '{item.get('Name')}' - last played "
                              f"{last_played:%Y-%m-%d}, older than {days} days")
                continue
            if not add(item, current=True):
                continue
            series_id = item.get("SeriesId")
            if item.get("Type") == "Episode" and series_id and series_id not in handled_series:
                handled_series.add(series_id)
                for upcoming in self._upcoming_episodes(item, user_id, number_episodes,
                                                        prefetch_minimum_minutes):
                    add(upcoming, current=False)
        return items

    def _upcoming_episodes(self, episode: Dict[str, Any], user_id: str, count: int,
                           minimum_minutes: int) -> List[Dict[str, Any]]:
        """Episodes after ``episode``: at least ``count``, extended to reach ``minimum_minutes``."""
        if count <= 0 and minimum_minutes <= 0:
            return []
        try:
            episodes = self._get(f"/Shows/{episode['SeriesId']}/Episodes", {
                "UserId": user_id, "StartItemId": episode["Id"], "Fields": ITEM_FIELDS,
                "IsMissing": "false", "EnableUserData": "true", "EnableImages": "false",
            }).get("Items", [])
        except Exception as e:
            _log_api_error(f"list episodes of '{episode.get('SeriesName')}'", e)
            return []

        upcoming, minutes = [], _runtime_minutes(episode)
        for ep in episodes:
            if ep.get("Id") == episode.get("Id") or not _item_path(ep):
                continue
            if len(upcoming) >= count and minutes >= minimum_minutes:
                break
            upcoming.append(ep)
            minutes += _runtime_minutes(ep)
        return upcoming

    # ------------------------------------------------------------- watchlist

    def get_watchlist_media(self, valid_sections: List[Any], watchlist_episodes: int,
                            users_toggle: bool, skip_watchlist: List[str],
                            rss_url: Optional[str] = None,
                            home_users: Optional[List[str]] = None
                            ) -> Generator[WatchlistTuple, None, None]:
        """Favorites (movies, series, single episodes) for each tracked user.

        Yields (file_path, username, watchlisted_at, episode_info, rating_key, media_type).
        Jellyfin does not record when an item was favorited, so watchlisted_at is
        None and watchlist retention counts from when PlexCache first saw it.
        """
        if rss_url:
            logging.debug("[JELLYFIN API] RSS watchlists are Plex-only; ignoring rss_url")
            return
        locations = self._allowed_locations(valid_sections)
        for username, user_id in self._users_for(users_toggle, skip_watchlist):
            try:
                yield from self._fetch_user_favorites(username, user_id, watchlist_episodes, locations)
            except Exception as e:
                _log_api_error(f"fetch favorites for {username}", e)
                self.mark_watchlist_incomplete()

    def _fetch_user_favorites(self, username: str, user_id: str, episodes_per_show: int,
                              locations: Optional[List[str]]) -> Generator[WatchlistTuple, None, None]:
        favorites = self._get(f"/Users/{user_id}/Items", {
            "Filters": "IsFavorite", "Recursive": "true",
            "IncludeItemTypes": "Movie,Series,Episode", "Fields": ITEM_FIELDS,
            "EnableUserData": "true", "EnableImages": "false",
        }).get("Items", [])
        logging.debug(f"[USER:{username}] {len(favorites)} favorites")

        for item in favorites:
            kind = item.get("Type")
            if kind == "Series":
                yield from self._favorite_series_episodes(item, username, user_id,
                                                          episodes_per_show, locations)
                continue
            if kind not in ("Movie", "Episode"):
                continue
            if (item.get("UserData") or {}).get("Played"):
                continue
            path = _item_path(item)
            if not path or not self._in_libraries(path, locations):
                continue
            media_type = "episode" if kind == "Episode" else "movie"
            info = _episode_info(item) if kind == "Episode" else None
            logging.debug(f"[USER:{username}] Favorite: {path}")
            yield (path, username, None, info, item.get("Id"), media_type)

    def _favorite_series_episodes(self, series: Dict[str, Any], username: str, user_id: str,
                                  count: int, locations: Optional[List[str]]
                                  ) -> Generator[WatchlistTuple, None, None]:
        """The next ``count`` unwatched episodes of a favorited series."""
        if count <= 0:
            return
        episodes = self._get(f"/Shows/{series['Id']}/Episodes", {
            "UserId": user_id, "Fields": ITEM_FIELDS, "IsMissing": "false",
            "EnableUserData": "true", "EnableImages": "false",
        }).get("Items", [])
        yielded = 0
        for ep in episodes:
            if yielded >= count:
                break
            if (ep.get("UserData") or {}).get("Played"):
                continue
            path = _item_path(ep)
            if not path or not self._in_libraries(path, locations):
                continue
            yielded += 1
            logging.debug(f"[USER:{username}] Favorite series '{series.get('Name')}': {path}")
            yield (path, username, None, _episode_info(ep), ep.get("Id"), "episode")
