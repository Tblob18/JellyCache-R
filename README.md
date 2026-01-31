# JellyCache-R V2.0: Automate Jellyfin Media Management
### Updated for Jellyfin - Fork Date: 1/7/2026

## Current Bugs / Todo List

Now moved to a discussion page [HERE](https://github.com/Tblob18/JellyCache-R/discussions)

## Overview
Automate Jellyfin media management: Efficiently transfer media from Continue Watching/Favorites to the cache, and seamlessly move watched media back to their respective locations.

JellyCache efficiently transfers media from Continue Watching and Favorites to the cache and moves watched media back to their respective locations. This Python script reduces energy consumption by minimizing the need to spin up the array/hard drive(s) when watching recurrent media like TV series. It achieves this by moving the media from Continue Watching and favorites for users. For TV shows/anime, it also fetches the next specified number of episodes.

## Features

- Fetch a specified number of episodes from "Continue Watching" for all users
- Skip fetching Continue Watching media for specified users
- Fetch episodes from "Favorites" for all users
- Skip fetching favorites media for specified users
- .plexcached backup system, so files are not moved off the array and are instead archived to prevent unnecessary move operations
- Search only the specified libraries
- Check for free space before moving any file
- Cache retention policies, with automatic removals based on age/priority settings
- Move watched media present on the cache drive back to the array
- Move respective subtitles along with the media moved to or from the cache
- Filter media older than a specified number of days
- Run in debug mode for testing
- Use of a log file for easy debugging
- Use caching system to avoid wasteful memory usage and cpu cycles
- Use of multitasking to optimize file transfer time
- Exit the script if any active session or skip the currently playing media
- Send Webhook messages according to set log level (untested)
- Unraid Mover exclusion file. This file also allows for manual custom entries 



  
### Core Modules

- **`config.py`**: Configuration management with dataclasses for type safety
- **`logging_config.py`**: Logging setup, rotation, and notification handlers
- **`system_utils.py`**: OS detection, path conversions, and file utilities
- **`jellyfin_api.py`**: Jellyfin server interactions and cache management
- **`file_operations.py`**: File moving, filtering, and subtitle operations
- **`plexcache_app.py`**: Main application orchestrator (named for compatibility, works with Jellyfin)



## Installation and Setup

This is a fork of the original PlexCache-R project, modified to work with Jellyfin instead of Plex. The setup process is similar, but you'll need:

1. **Jellyfin server URL** (e.g., `http://localhost:8096`)
2. **Jellyfin API Key** - Generate this in Jellyfin Dashboard → API Keys
3. **Path mappings** - Configure how Jellyfin paths map to your actual filesystem

### Quick Start

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `jellycache_settings.json` file based on the example below
4. Run the script: `python3 plexcache_app.py`

### Configuration Example

Create `jellycache_settings.json` (or `plexcache_settings.json` for backwards compatibility):

```json
{
  "jellyfin_url": "http://localhost:8096",
  "api_key": "your_jellyfin_api_key_here",
  "valid_sections": [],
  "number_episodes": 10,
  "days_to_monitor": 7,
  "users_toggle": true,
  "skip_ondeck": [],
  "skip_favorites": [],
  "favorites_toggle": true,
  "favorites_episodes": 5,
  "watched_move": true,
  "cache_retention_hours": 12,
  "favorites_retention_days": 0,
  "cache_limit": "",
  "cache_dir": "/mnt/cache/media/",
  "path_mappings": [
    {
      "name": "TV Shows",
      "plex_path": "/data/tv/",
      "real_path": "/mnt/array/tv/",
      "cache_path": "/mnt/cache/tv/",
      "cacheable": true,
      "enabled": true
    },
    {
      "name": "Movies",
      "plex_path": "/data/movies/",
      "real_path": "/mnt/array/movies/",
      "cache_path": "/mnt/cache/movies/",
      "cacheable": true,
      "enabled": true
    }
  ],
  "max_concurrent_moves_array": 2,
  "max_concurrent_moves_cache": 5,
  "notification_type": "system"
}
```

## Notes

This script has been tested on Unraid with Jellyfin as a Docker container. It should work on other Linux-based systems, but your mileage may vary. 

**Key Differences from PlexCache:**
- Uses Jellyfin's "Continue Watching" instead of Plex's "OnDeck"
- Uses Jellyfin's "Favorites" instead of Plex's "Watchlist"
- No RSS feed support for remote users (Jellyfin favorites are per-user)
- Authentication uses Jellyfin API keys instead of Plex tokens

## Disclaimer

This script comes without any warranties, guarantees, or magic powers. By using this script, you accept that you're responsible for any consequences that may result. The author will not be held liable for data loss, corruption, or any other problems you may encounter. So, it's on you to make sure you have backups and test this script thoroughly before you unleash its awesome power.

## Acknowledgments

**This is a fork of PlexCache-R**, modified to work with Jellyfin instead of Plex. Special thanks to:

- The original PlexCache-R contributors at [StudioNirin/PlexCache-R](https://github.com/StudioNirin/PlexCache-R) (upstream project)
- brimur[^3] for providing the foundational script
- bexem[^4] for early iterations
- bbergle[^5] for major refactoring work
- [Brandon-Haney](https://github.com/Brandon-Haney) for contributions to PlexCache-R

This Jellyfin fork was created to bring the same power-saving benefits to Jellyfin users!

[^3]: [brimur/preCachePlexOnDeckEpiosodes.py](https://gist.github.com/brimur/95277e75ca399d5d52b61e6aa192d1cd)
[^4]: https://github.com/bexem/PlexCache
[^5]: https://github.com/BBergle/PlexCache




