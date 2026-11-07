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

### Web UI (recommended)

* **Setup wizard**, step 2: pick **Jellyfin**, enter the URL and an API key,
  *Test Connection*, then continue. Libraries, path mappings and users come
  from Jellyfin in the following steps.
* **Settings > Media Server** switches an existing install between Plex and
  Jellyfin. After switching, re-check **Libraries** and **Users** (use
  *Sync users*), since both come from the selected server.

### Settings file

Set `media_server` to `jellyfin` and provide `JELLYFIN_URL` + `JELLYFIN_API_KEY`
instead of `PLEX_URL` / `PLEX_TOKEN`. See
[`example_settings_jellyfin.json`](example_settings_jellyfin.json).

* **API key**: Jellyfin Dashboard > API Keys > `+`. One key reads every user's
  progress; there are no per-user tokens.
* **`valid_sections`**: Jellyfin libraries, as the integer id the web UI
  writes (a stable CRC32 of the library GUID), the library GUID, or the
  library **name** (e.g. `"Movies"`). Empty list = all libraries.
* **`path_mappings[].plex_path`**: the path *as Jellyfin sees it* (inside the
  Jellyfin container, e.g. `/data/movies/`). `real_path` is the Unraid path
  (`/mnt/user/media/movies/`), `cache_path` the pool path
  (`/mnt/cache/media/movies/`).
* **Users**: every enabled Jellyfin user is tracked unless their entry has
  `"skip_ondeck": true` / `"skip_watchlist": true`. New users are added
  automatically with tracking on.

## Testing your setup: Moves and Stats

Every run writes each decision to `data/move_journal.jsonl` (kept 30 days,
`move_journal_retention_days`): what was cached, moved back, evicted,
released, skipped or held, the outcome, and **why** - e.g.

| Action | Reason |
|---|---|
| Cached | *Upcoming episode after Show S01E02 (paul) - prefetched so the next episode plays from cache* |
| Moved back | *Show S01E02 is no longer in any user's watch window (already watched, or outside the prefetch range)* |
| Held | *... - kept for cache retention, 5h left* |
| Skipped | *... priority score (31) is below the eviction minimum (40) - it would be evicted again* |

* **Moves** page: filter by run, action, outcome, reason, user or text; CSV export.
* **Stats** page: totals, data moved per day, why files moved, per user, top
  shows, *churn* (files that bounced between cache and array - a sign that
  retention or prefetch is too tight) and failures.
* **Playing now** (top of Stats): every active session and whether it is
  served **from cache** (array disks can sleep) or **from array**. This is the
  quickest check that caching works for what you actually watch. Click
  *history* to see why that file is where it is.

Suggested loop: change a setting, start a **dry run** from the dashboard, and
read its run in **Moves** - nothing is touched, but every decision and reason
is recorded.

## Not supported with Jellyfin

* Pinned media, Recently Added, remote watchlist RSS, the Plex DB fallback and
  Plex OAuth login are Plex-only; they are hidden or skipped.
* Jellyfin has no "favorited at" date, so watchlist retention counts from when
  PlexCache first saw the favorite.
