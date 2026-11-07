# Jellyfin support (JellyCache-R)

JellyCache-R is PlexCache-D with a Jellyfin backend. Everything below the media
server — caching, `.plexcached` backups, eviction, Unraid mover exclusions,
sibling files (subtitles/artwork/NFOs), the scheduler — is upstream code and
behaves the same. Only *what to cache* comes from Jellyfin instead of Plex.

## What gets cached

| Plex concept | Jellyfin equivalent used |
|---|---|
| OnDeck | **Continue Watching** (partially watched movies/episodes) + **Next Up** |
| next `number_episodes` | the next N episodes after the one in progress (`prefetch_minimum_minutes` still extends this) |
| Watchlist | **Favorites**: favorited movies, favorited episodes, and the next `watchlist_episodes` *unwatched* episodes of favorited series |
| `days_to_monitor` | items whose last play is older than this are ignored (per-user overrides work) |
| Active sessions | `/Sessions` — files currently playing are never moved |

When something leaves Continue Watching / Favorites (you finished it, or
unfavorited it) and `watched_move` is on, it is moved back to the array on the
next run — exactly like upstream.

## Configuration

Set `media_server` to `jellyfin` and provide `JELLYFIN_URL` + `JELLYFIN_API_KEY`
instead of `PLEX_URL` / `PLEX_TOKEN`. See
[`example_settings_jellyfin.json`](example_settings_jellyfin.json).

* **API key**: Jellyfin Dashboard → API Keys → `+`. One key reads every user's
  progress; there are no per-user tokens.
* **`valid_sections`**: list of Jellyfin library **names** (e.g. `"Movies"`)
  or library ItemIds. Empty list = all libraries.
* **`path_mappings[].plex_path`**: the path *as Jellyfin sees it* (inside the
  Jellyfin container, e.g. `/data/movies/`). `real_path` is the Unraid path
  (`/mnt/user/media/movies/`), `cache_path` the pool path
  (`/mnt/cache/media/movies/`).
* **Users**: all enabled Jellyfin users are tracked and auto-added to `users`
  on first run. Set `"skip_ondeck": true` / `"skip_watchlist": true` on a user
  entry to exclude them.

## Not (yet) supported with Jellyfin

* Web UI setup wizard / Plex settings page are still Plex-only — configure
  `plexcache_settings.json` by hand. The rest of the web UI (dashboard, cache
  browser, maintenance, logs, scheduler) works.
* Don't save the web UI *Libraries* page — it expects numeric Plex section ids.
* Pinned media, Recently Added, remote watchlist RSS, Plex DB fallback and Plex
  OAuth login are Plex-only and are skipped.
