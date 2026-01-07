"""
Jellyfin API integration for JellyCache.
Handles Jellyfin server connections and media fetching operations.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Generator, Tuple, Dict, Set
from dataclasses import dataclass

import requests


@dataclass
class OnDeckItem:
    """Represents a Continue Watching item with metadata.

    Attributes:
        file_path: Path to the media file.
        username: The user who has this on their Continue Watching.
        episode_info: For TV episodes, dict with 'show', 'season', 'episode' keys.
        is_current_ondeck: True if this is the actual resume episode (not prefetched next).
    """
    file_path: str
    username: str
    episode_info: Optional[Dict[str, any]] = None
    is_current_ondeck: bool = False


# API delay between jellyfin calls (seconds)
JELLYFIN_API_DELAY = 0.5


def _log_api_error(context: str, error: Exception) -> None:
    """Log API errors with specific detection for common HTTP status codes."""
    error_str = str(error)

    if "401" in error_str or "Unauthorized" in error_str:
        logging.error(f"[JELLYFIN API] Authentication failed ({context}): {error}")
        logging.error(f"[JELLYFIN API] Your Jellyfin API key is invalid or has been revoked.")
        logging.error(f"[JELLYFIN API] To fix: Run 'python3 jellycache_setup.py' and re-authenticate.")
    elif "429" in error_str or "Too Many Requests" in error_str:
        logging.warning(f"[JELLYFIN API] Rate limited ({context}): {error}")
        logging.warning(f"[JELLYFIN API] Consider increasing delays between API calls")
    elif "403" in error_str or "Forbidden" in error_str:
        logging.error(f"[JELLYFIN API] Access forbidden ({context}): {error}")
        logging.error(f"[JELLYFIN API] User may not have permission for this resource")
    elif "404" in error_str or "Not Found" in error_str:
        logging.warning(f"[JELLYFIN API] Resource not found ({context}): {error}")
    elif "500" in error_str or "502" in error_str or "503" in error_str:
        logging.error(f"[JELLYFIN API] Jellyfin server error ({context}): {error}")
        logging.error(f"[JELLYFIN API] Server may be experiencing issues")
    else:
        logging.error(f"[JELLYFIN API] Error ({context}): {error}")


class UserProxy:
    """Simple proxy object to pass username to methods expecting a user object."""

    def __init__(self, title: str, user_id: str):
        self.title = title
        self.id = user_id


class JellyfinManager:
    """Manages Jellyfin server connections and operations."""

    def __init__(self, jellyfin_url: str, api_key: str, retry_limit: int = 3, delay: int = 5):
        self.jellyfin_url = jellyfin_url.rstrip('/')
        self.api_key = api_key
        self.retry_limit = retry_limit
        self.delay = delay
        self._users_cache: Dict[str, Dict] = {}  # username -> {id, ...}
        self._users_loaded = False
        self._api_lock = threading.Lock()
        self._jellyfin_reachable = True
        self._favorites_data_complete = True  # Track if we got complete favorites data

    def connect(self) -> None:
        """Connect to the Jellyfin server and verify access."""
        logging.debug(f"Connecting to Jellyfin server: {self.jellyfin_url}")

        try:
            # Test connection by getting system info
            response = self._make_request("GET", "/System/Info")
            server_name = response.get("ServerName", "Unknown")
            version = response.get("Version", "Unknown")
            logging.debug(f"Jellyfin server: {server_name}, version: {version}")
        except Exception as e:
            _log_api_error("connect to Jellyfin server", e)
            raise ConnectionError(f"Error connecting to the Jellyfin server: {e}")

    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """Make an authenticated API request to Jellyfin.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/Users")
            params: URL query parameters
            data: Request body data (for POST/PUT)
            
        Returns:
            Response data as dict
        """
        url = f"{self.jellyfin_url}{endpoint}"
        headers = {
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            
            # Return empty dict for successful responses with no content
            if not response.content:
                return {}
                
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")

    def _rate_limited_api_call(self) -> None:
        """Enforce rate limiting for Jellyfin API calls."""
        with self._api_lock:
            time.sleep(JELLYFIN_API_DELAY)

    def load_user_tokens(self, skip_users: Optional[List[str]] = None,
                         settings_users: Optional[List[dict]] = None,
                         main_username: Optional[str] = None) -> Dict[str, str]:
        """Load and cache user information.
        
        For Jellyfin, we don't need per-user tokens like Plex - the admin API key
        can access all user data. This method loads user IDs for user filtering.
        
        Args:
            skip_users: List of usernames to skip
            settings_users: Not used for Jellyfin (kept for compatibility)
            main_username: Not used for Jellyfin (kept for compatibility)
            
        Returns:
            Dict mapping username -> user_id
        """
        if self._users_loaded:
            logging.debug("[JELLYFIN API] User info already loaded, using cached values")
            return {u['name']: u['id'] for u in self._users_cache.values()}

        skip_users = skip_users or []
        logging.debug("[JELLYFIN API] Loading user information...")

        try:
            self._rate_limited_api_call()
            users_response = self._make_request("GET", "/Users")
            
            user_count = 0
            for user in users_response:
                username = user.get("Name", "")
                user_id = user.get("Id", "")
                
                if not username or not user_id:
                    continue
                    
                if username in skip_users:
                    logging.debug(f"[USER:{username}] Skipping (in skip list)")
                    continue
                
                self._users_cache[username] = {
                    'id': user_id,
                    'name': username
                }
                user_count += 1
                logging.debug(f"[USER:{username}] Loaded (ID: {user_id})")
            
            self._users_loaded = True
            logging.info(f"Connected to Jellyfin ({user_count} users)")
            if self._users_cache:
                user_names = sorted(self._users_cache.keys(), key=str.lower)
                logging.info(f"USERS: {', '.join(user_names)}")
                
            return {u['name']: u['id'] for u in self._users_cache.values()}
            
        except Exception as e:
            _log_api_error("load user information", e)
            self._jellyfin_reachable = False
            self._favorites_data_complete = False
            logging.warning("[JELLYFIN API] Failed to load users - using limited functionality")
            return {}

    def get_user_id(self, username: str) -> Optional[str]:
        """Get user ID for a username."""
        user_info = self._users_cache.get(username)
        return user_info['id'] if user_info else None

    def is_jellyfin_reachable(self) -> bool:
        """Check if Jellyfin server was reachable during user loading."""
        return self._jellyfin_reachable

    def is_favorites_data_complete(self) -> bool:
        """Check if favorites data is complete (no fetch failures)."""
        return self._favorites_data_complete

    def mark_favorites_incomplete(self) -> None:
        """Mark favorites data as incomplete (e.g., after fetch failure)."""
        self._favorites_data_complete = False

    def get_active_sessions(self) -> List:
        """Get active sessions from Jellyfin."""
        try:
            self._rate_limited_api_call()
            sessions = self._make_request("GET", "/Sessions")
            # Filter to only sessions that are currently playing something
            active_sessions = [s for s in sessions if s.get("NowPlayingItem")]
            return active_sessions
        except Exception as e:
            _log_api_error("get active sessions", e)
            return []

    def get_media_file_path(self, item_id: str) -> Optional[str]:
        """Get the file path for a media item.
        
        Args:
            item_id: Jellyfin item ID
            
        Returns:
            File path or None if not found
        """
        try:
            self._rate_limited_api_call()
            # Get item details
            item = self._make_request("GET", f"/Users/{list(self._users_cache.values())[0]['id']}/Items/{item_id}")
            
            # Navigate to the file path
            path = item.get("Path")
            if path:
                return path
                
            # Try MediaSources for path
            media_sources = item.get("MediaSources", [])
            if media_sources and len(media_sources) > 0:
                return media_sources[0].get("Path")
                
            logging.debug(f"No file path found for item {item_id}")
            return None
            
        except Exception as e:
            logging.debug(f"Error getting file path for item {item_id}: {e}")
            return None

    def get_on_deck_media(self, valid_sections: List[int], days_to_monitor: int,
                        number_episodes: int, users_toggle: bool, skip_ondeck: List[str]) -> List[OnDeckItem]:
        """Get Continue Watching media files (equivalent to Plex OnDeck).

        Returns:
            List of OnDeckItem objects containing file path, username, and episode metadata.
        """
        on_deck_files: List[OnDeckItem] = []

        # Build list of users to fetch
        users_to_fetch = []
        if users_toggle:
            for username, user_info in self._users_cache.items():
                if username in skip_ondeck:
                    logging.info(f"[USER:{username}] Skipping for Continue Watching — in skip list")
                    continue
                users_to_fetch.append(UserProxy(username, user_info['id']))
        else:
            # Just use first user if no multi-user support
            if self._users_cache:
                first_user = list(self._users_cache.values())[0]
                users_to_fetch.append(UserProxy(first_user['name'], first_user['id']))

        logging.debug(f"Fetching Continue Watching media for {len(users_to_fetch)} users")

        # Fetch concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self._fetch_user_on_deck_media,
                    user, days_to_monitor, number_episodes
                )
                for user in users_to_fetch
            }

            for future in as_completed(futures):
                try:
                    on_deck_files.extend(future.result())
                except Exception as e:
                    logging.error(f"An error occurred while fetching Continue Watching media for a user: {e}")

        # Log items grouped by user
        items_by_user: Dict[str, List[OnDeckItem]] = {}
        for item in on_deck_files:
            if item.username not in items_by_user:
                items_by_user[item.username] = []
            items_by_user[item.username].append(item)

        for username in sorted(items_by_user.keys()):
            items = items_by_user[username]
            for item in items:
                logging.debug(f"[USER:{username}] Continue Watching found: {item.file_path}")
            logging.debug(f"[USER:{username}] Found {len(items)} Continue Watching items")

        return on_deck_files

    def _fetch_user_on_deck_media(self, user: UserProxy, days_to_monitor: int,
                                 number_episodes: int) -> List[OnDeckItem]:
        """Fetch Continue Watching media for a specific user.

        Returns:
            List of OnDeckItem objects containing file path, username, and episode metadata.
        """
        username = user.title
        user_id = user.id
        
        try:
            logging.debug(f"[USER:{username}] Fetching Continue Watching media...")

            on_deck_files: List[OnDeckItem] = []
            
            self._rate_limited_api_call()
            # Get resume items (Continue Watching)
            resume_items = self._make_request("GET", f"/Users/{user_id}/Items/Resume", {
                "Limit": 50,
                "Fields": "Path,MediaSources,ParentId"
            })
            
            items = resume_items.get("Items", [])
            
            for item in items:
                item_type = item.get("Type", "")
                last_played = item.get("UserData", {}).get("LastPlayedDate")
                
                # Check if item was played recently
                if last_played:
                    try:
                        last_played_dt = datetime.fromisoformat(last_played.replace('Z', '+00:00'))
                        days_since_played = (datetime.now(last_played_dt.tzinfo) - last_played_dt).days
                        if days_since_played > days_to_monitor:
                            continue
                    except Exception:
                        pass
                
                if item_type == "Episode":
                    self._process_episode_ondeck(item, user_id, number_episodes, on_deck_files, username)
                elif item_type == "Movie":
                    self._process_movie_ondeck(item, on_deck_files, username)
                else:
                    logging.debug(f"Skipping Continue Watching item '{item.get('Name')}' — unknown type {item_type}")

            return on_deck_files

        except Exception as e:
            _log_api_error(f"fetch Continue Watching for {username}", e)
            return []

    def _process_episode_ondeck(self, item: dict, user_id: str, number_episodes: int, 
                                on_deck_files: List[OnDeckItem], username: str = "unknown") -> None:
        """Process an episode from Continue Watching.

        Args:
            item: The episode item from API.
            user_id: User ID for fetching more episodes.
            number_episodes: Number of next episodes to fetch.
            on_deck_files: List to append OnDeckItem objects to.
            username: The user who has this on Continue Watching.
        """
        show_name = item.get("SeriesName", "")
        season_number = item.get("ParentIndexNumber")
        episode_number = item.get("IndexNumber")
        
        # Get file path
        file_path = item.get("Path")
        if not file_path:
            media_sources = item.get("MediaSources", [])
            if media_sources:
                file_path = media_sources[0].get("Path")
        
        if not file_path:
            logging.warning(f"No file path found for episode: {show_name}")
            return
        
        # Create episode info dict
        episode_info = None
        if season_number is not None and episode_number is not None:
            episode_info = {
                'show': show_name,
                'season': season_number,
                'episode': episode_number
            }
        
        # Add the current episode
        on_deck_files.append(OnDeckItem(
            file_path=file_path,
            username=username,
            episode_info=episode_info,
            is_current_ondeck=True
        ))
        
        # Fetch next episodes if we have valid season/episode numbers
        if season_number is None or episode_number is None:
            logging.warning(f"Skipping next episode fetch for '{show_name}' - missing index data")
            return
        
        # Get the series ID
        series_id = item.get("SeriesId")
        if not series_id:
            logging.debug(f"No series ID for {show_name}, cannot fetch next episodes")
            return
        
        try:
            # Get all episodes from the series
            self._rate_limited_api_call()
            all_episodes_response = self._make_request("GET", f"/Shows/{series_id}/Episodes", {
                "UserId": user_id,
                "Fields": "Path,MediaSources,ParentIndexNumber,IndexNumber"
            })
            
            all_episodes = all_episodes_response.get("Items", [])
            next_episodes = self._get_next_episodes(all_episodes, season_number, episode_number, number_episodes)
            
            # Add prefetched next episodes
            for next_ep in next_episodes:
                next_file_path = next_ep.get("Path")
                if not next_file_path:
                    media_sources = next_ep.get("MediaSources", [])
                    if media_sources:
                        next_file_path = media_sources[0].get("Path")
                
                if not next_file_path:
                    continue
                
                next_ep_info = {
                    'show': show_name,
                    'season': next_ep.get("ParentIndexNumber"),
                    'episode': next_ep.get("IndexNumber")
                }
                
                on_deck_files.append(OnDeckItem(
                    file_path=next_file_path,
                    username=username,
                    episode_info=next_ep_info,
                    is_current_ondeck=False
                ))
                
        except Exception as e:
            logging.debug(f"Error fetching next episodes for {show_name}: {e}")

    def _process_movie_ondeck(self, item: dict, on_deck_files: List[OnDeckItem], username: str = "unknown") -> None:
        """Process a movie from Continue Watching.

        Args:
            item: The movie item from API.
            on_deck_files: List to append OnDeckItem objects to.
            username: The user who has this on Continue Watching.
        """
        file_path = item.get("Path")
        if not file_path:
            media_sources = item.get("MediaSources", [])
            if media_sources:
                file_path = media_sources[0].get("Path")
        
        if not file_path:
            logging.warning(f"No file path found for movie: {item.get('Name')}")
            return
        
        on_deck_files.append(OnDeckItem(
            file_path=file_path,
            username=username,
            episode_info=None,
            is_current_ondeck=True
        ))

    def _get_next_episodes(self, episodes: List[dict], current_season: int,
                          current_episode_index: int, number_episodes: int) -> List[dict]:
        """Get the next episodes after the current one."""
        next_episodes = []
        for episode in episodes:
            season_num = episode.get("ParentIndexNumber")
            episode_num = episode.get("IndexNumber")
            
            if season_num is None or episode_num is None:
                continue
            
            if (season_num > current_season or
                (season_num == current_season and episode_num > current_episode_index)):
                next_episodes.append(episode)
                if len(next_episodes) >= number_episodes:
                    break
        
        return next_episodes

    def get_favorites_media(self, valid_sections: List[int], favorites_episodes: int,
                           users_toggle: bool, skip_favorites: List[str]) -> Generator[Tuple[str, str, Optional[datetime]], None, None]:
        """Get favorites media files (equivalent to Plex Watchlist).

        Yields:
            Tuples of (file_path, username, favorited_at)
        """
        # Build list of users to fetch
        users_to_fetch = []
        if users_toggle:
            for username, user_info in self._users_cache.items():
                if username in skip_favorites:
                    logging.info(f"[USER:{username}] Skipping for Favorites — in skip list")
                    continue
                users_to_fetch.append(UserProxy(username, user_info['id']))
        else:
            # Just use first user if no multi-user support
            if self._users_cache:
                first_user = list(self._users_cache.values())[0]
                users_to_fetch.append(UserProxy(first_user['name'], first_user['id']))

        logging.debug(f"Processing {len(users_to_fetch)} users for favorites")

        # Fetch favorites for each user
        for user in users_to_fetch:
            try:
                yield from self._fetch_user_favorites(user, favorites_episodes)
            except Exception as e:
                logging.error(f"[USER:{user.title}] Error fetching favorites: {e}")
                self.mark_favorites_incomplete()

    def _fetch_user_favorites(self, user: UserProxy, favorites_episodes: int) -> Generator[Tuple[str, str, Optional[datetime]], None, None]:
        """Fetch favorites for a specific user.

        Yields:
            Tuples of (file_path, username, favorited_at)
        """
        username = user.title
        user_id = user.id
        
        logging.debug(f"[USER:{username}] Fetching favorites media")
        
        try:
            self._rate_limited_api_call()
            # Get favorite items
            favorites_response = self._make_request("GET", f"/Users/{user_id}/Items", {
                "Filters": "IsFavorite",
                "Recursive": "true",
                "Fields": "Path,MediaSources,DateCreated",
                "IncludeItemTypes": "Movie,Series"
            })
            
            items = favorites_response.get("Items", [])
            logging.debug(f"[USER:{username}] Found {len(items)} favorite items")
            
            for item in items:
                item_type = item.get("Type", "")
                favorited_at = None
                
                # Try to get date created as a proxy for favorited date
                date_created = item.get("DateCreated")
                if date_created:
                    try:
                        favorited_at = datetime.fromisoformat(date_created.replace('Z', '+00:00'))
                    except Exception:
                        pass
                
                if item_type == "Series":
                    yield from self._process_favorites_show(item, user_id, favorites_episodes, username, favorited_at)
                elif item_type == "Movie":
                    yield from self._process_favorites_movie(item, username, favorited_at)
                else:
                    logging.debug(f"Ignoring favorite item '{item.get('Name')}' of type '{item_type}'")
                    
        except Exception as e:
            logging.error(f"[USER:{username}] Error fetching favorites: {e}")
            self.mark_favorites_incomplete()

    def _process_favorites_show(self, item: dict, user_id: str, favorites_episodes: int,
                               username: str, favorited_at: Optional[datetime]) -> Generator[Tuple[str, str, Optional[datetime]], None, None]:
        """Process a favorited show and yield episode file paths."""
        series_id = item.get("Id")
        show_name = item.get("Name", "")
        
        try:
            self._rate_limited_api_call()
            # Get episodes from the series
            episodes_response = self._make_request("GET", f"/Shows/{series_id}/Episodes", {
                "UserId": user_id,
                "Fields": "Path,MediaSources",
                "Limit": favorites_episodes
            })
            
            episodes = episodes_response.get("Items", [])
            logging.debug(f"Processing show {show_name} with {len(episodes)} episodes (limit: {favorites_episodes})")
            
            yielded_count = 0
            skipped_watched = 0
            skipped_no_path = 0
            
            for episode in episodes:
                # Check if already watched
                user_data = episode.get("UserData", {})
                if user_data.get("Played", False):
                    skipped_watched += 1
                    continue
                
                # Get file path
                file_path = episode.get("Path")
                if not file_path:
                    media_sources = episode.get("MediaSources", [])
                    if media_sources:
                        file_path = media_sources[0].get("Path")
                
                if not file_path:
                    skipped_no_path += 1
                    continue
                
                logging.debug(f"[USER:{username}] Favorites found: {file_path}")
                yield (file_path, username, favorited_at)
                yielded_count += 1
            
            if skipped_watched > 0:
                logging.debug(f"  {show_name}: {yielded_count} episodes to cache, {skipped_watched} skipped (already watched)")
            if skipped_no_path > 0:
                logging.warning(f"  {show_name}: {skipped_no_path} episodes skipped (no file path)")
                
        except Exception as e:
            logging.warning(f"Error processing show '{show_name}': {e}")

    def _process_favorites_movie(self, item: dict, username: str,
                                favorited_at: Optional[datetime]) -> Generator[Tuple[str, str, Optional[datetime]], None, None]:
        """Process a favorited movie and yield file path."""
        file_path = item.get("Path")
        if not file_path:
            media_sources = item.get("MediaSources", [])
            if media_sources:
                file_path = media_sources[0].get("Path")
        
        if not file_path:
            logging.warning(f"No file path found for movie: {item.get('Name')}")
            return
        
        logging.debug(f"[USER:{username}] Favorites found: {file_path}")
        yield (file_path, username, favorited_at)
