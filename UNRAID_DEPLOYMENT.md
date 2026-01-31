# JellyCache-R Unraid Deployment Guide

This guide walks you through deploying JellyCache-R on Unraid to automatically cache actively watched media on your SSD.

## Prerequisites

- Unraid server with Docker support
- Jellyfin running (with API key)
- SSD cache drive configured
- SSH or terminal access to Unraid
- Git installed (recommended) or ability to transfer files via SCP

## Quick Start

### 1. Create the appdata directory

```bash
mkdir -p /mnt/user/appdata/jellycache/logs
```

### 2. Clone or copy the repository

**Option A: Clone the repository (Recommended)**

```bash
cd /mnt/user/appdata
git clone https://github.com/Tblob18/JellyCache-R.git jellycache
```

**Option B: Copy files manually**

If you can't use git, copy ALL these files to `/mnt/user/appdata/jellycache/`:

```bash
# Required files (from your local machine):
scp Dockerfile docker-compose.yml requirements.txt root@YOUR_UNRAID_IP:/mnt/user/appdata/jellycache/
scp *.py root@YOUR_UNRAID_IP:/mnt/user/appdata/jellycache/
scp jellycache_settings.example.json root@YOUR_UNRAID_IP:/mnt/user/appdata/jellycache/
```

> **Important**: The Dockerfile requires all Python files (`plexcache_app.py`, `config.py`, `jellyfin_api.py`, `file_operations.py`, `logging_config.py`, `system_utils.py`) and `requirements.txt` to be present in the build directory.

### 3. Create configuration file

Copy the example config and customize it:

```bash
cd /mnt/user/appdata/jellycache
cp jellycache_settings.example.json jellycache_settings.json
```

Then edit the file and replace:
- `YOUR_JELLYFIN_IP` with your Jellyfin server IP
- `YOUR_JELLYFIN_API_KEY` with your API key (Dashboard > API Keys)
- `YOUR_SHARE` with your Unraid share name (e.g., `Vault`)

### 4. Verify your path mappings

Edit `/mnt/user/appdata/jellycache/jellycache_settings.json` and ensure:

- `plex_path` matches what Jellyfin sees inside its container (check Jellyfin > Dashboard > Libraries)
  > **Note**: The field is named `plex_path` for backwards compatibility with the original PlexCache-R project. It refers to the path as seen by Jellyfin inside its Docker container.
- `real_path` is the actual array path (`/mnt/user/...`)
- `cache_path` is the cache equivalent (`/mnt/cache/...`)

Example for German folder names:
```json
"path_mappings": [
    {
        "name": "TV Shows",
        "plex_path": "/data/tvshows/",
        "real_path": "/mnt/user/Vault/Media/Serien/",
        "cache_path": "/mnt/cache/Vault/Media/Serien/",
        "cacheable": true,
        "enabled": true,
        "_comment": "plex_path is the path Jellyfin sees inside its container"
    },
    {
        "name": "Movies",
        "plex_path": "/data/movies/",
        "real_path": "/mnt/user/Vault/Media/Filme/",
        "cache_path": "/mnt/cache/Vault/Media/Filme/",
        "cacheable": true,
        "enabled": true
    }
]
```

### 5. Test with dry-run

```bash
# IMPORTANT: You must be in the directory containing docker-compose.yml
cd /mnt/user/appdata/jellycache

# Verify you're in the right place
ls docker-compose.yml

# Run with dry-run (Docker Compose V2 syntax - use this on newer systems)
docker compose run --rm jellycache python plexcache_app.py --config /config/jellycache_settings.json --dry-run --verbose

# Or if using older Docker Compose V1 (with hyphen):
# docker-compose run --rm jellycache python plexcache_app.py --config /config/jellycache_settings.json --dry-run --verbose
```

> **Note**: The path `/config/jellycache_settings.json` is the path *inside the Docker container*. The docker-compose.yml mounts your host file (`/mnt/user/appdata/jellycache/jellycache_settings.json`) to this container path.

> **Troubleshooting**: If you get `no configuration file provided: not found`, you're either not in the correct directory or need to use `docker compose` (with space) instead of `docker-compose` (with hyphen).

### 6. Run for real

Once dry-run looks good:

```bash
cd /mnt/user/appdata/jellycache
docker compose up --build
```

## Scheduled Execution

JellyCache-R is designed to run periodically (not as a daemon). Use one of these methods:

### Option A: User Scripts Plugin (Recommended)

1. Install "User Scripts" from Community Applications
2. Add a new script named `jellycache`
3. Set schedule (e.g., every 6 hours, or daily at midnight)
4. Script content:

```bash
#!/bin/bash
cd /mnt/user/appdata/jellycache
docker compose up --build 2>&1
```

### Option B: Cron

Add to `/boot/config/go` (persists across reboots):

```bash
# Run every 6 hours
echo "0 */6 * * * cd /mnt/user/appdata/jellycache && docker compose up --build >> /mnt/user/appdata/jellycache/logs/cron.log 2>&1" >> /var/spool/cron/crontabs/root
```

## Configuration Reference

### Required Settings

| Setting | Description | Example |
|---------|-------------|---------|
| `jellyfin_url` | URL to your Jellyfin server | `"http://192.168.1.100:8096"` |
| `api_key` | Jellyfin API key (Dashboard > API Keys) | `"your_api_key_here"` |
| `path_mappings` | Array of path mappings (see above) | See example |

### Caching Behavior

| Setting | Description | Default | Recommended |
|---------|-------------|---------|-------------|
| `days_to_monitor` | How far back to look at watch history | 7 | 7-14 days |
| `cache_retention_hours` | Hours to keep items after leaving Continue Watching | 12 | 72 (3 days) |
| `number_episodes` | Episodes to cache ahead for TV shows (Continue Watching) | 5 | 5-10 |
| `favorites_toggle` | Enable caching of favorited items | `true` | `true` |
| `favorites_episodes` | Episodes to cache for favorited TV shows | 3 | 3-5 |
| `favorites_retention_days` | Days to keep favorited items (0 = forever) | 0 | 7 |
| `watchlist_toggle` | Enable caching of watchlist items | `true` | `true` |
| `watchlist_episodes` | Episodes to cache for watchlist TV shows | 3 | 3 |
| `watched_move` | Move fully watched items back to array | `true` | `true` |

### User Filtering

| Setting | Description | Default |
|---------|-------------|---------|
| `users_toggle` | Process all users (true) or only configured ones | `true` |
| `skip_ondeck` | Array of usernames to skip for Continue Watching | `[]` |
| `skip_favorites` | Array of usernames to skip for Favorites | `[]` |

### File Operations

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| `hardlinked_files` | How to handle hardlinked files (seeding torrents) | `"skip"` | `"skip"`, `"copy"`, `"move"` |
| `move_method` | File transfer method | `"move"` | `"move"`, `"copy"` |
| `preserve_timestamps` | Keep original file timestamps | `true` | `true`/`false` |
| `verify_moves` | Verify file integrity after move | `true` | `true`/`false` |
| `create_plexcached_backups` | Create .plexcached backup files | `true` | `true`/`false` |
| `exit_if_active_session` | Stop if media is currently playing | `false` | `true`/`false` |

### Performance

| Setting | Description | Default |
|---------|-------------|---------|
| `max_concurrent_moves_array` | Parallel file moves to array (HDD) | 2 |
| `max_concurrent_moves_cache` | Parallel file moves to cache (SSD) | 3 |
| `cache_limit` | Max cache space (e.g., `"250GB"`, `"50%"`, or `""` for unlimited) | `""` |

### Notifications

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| `notification_type` | How to send notifications | `"system"` | `"system"`, `"unraid"`, `"webhook"`, `"both"` |
| `log_level` | Logging verbosity | `"INFO"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |

## How It Works

1. **Caching**: Files are copied to `/mnt/cache/...`, originals renamed to `.plexcached`
2. **Unraid fusion**: `/mnt/user/` transparently shows cache copies
3. **Jellyfin**: Sees the same path, but reads from SSD instead of HDD
4. **Uncaching**: When retention expires, `.plexcached` is renamed back, cache copy deleted

## Troubleshooting

### Check logs

```bash
cat /mnt/user/appdata/jellycache/logs/plexcache.log
```

### Verify Jellyfin API

```bash
curl -s "http://YOUR_JELLYFIN_IP:8096/Users?api_key=YOUR_API_KEY"
```

### Check what's in Continue Watching

```bash
curl -s "http://YOUR_JELLYFIN_IP:8096/Users/YOUR_USER_ID/Items/Resume?api_key=YOUR_API_KEY&Limit=10&Fields=Path"
```

### Common issues

1. **"Path not found"**: Check that volume mounts in docker-compose.yml match your actual paths
2. **"API error"**: Verify Jellyfin URL and API key in settings
3. **"Permission denied"**: Ensure PUID/PGID match your Unraid user (99/100 for nobody/users)

## File Structure on Unraid

After setup, your directory should look like this:

```
/mnt/user/appdata/jellycache/
├── jellycache_settings.json       # Your configuration (create from example)
├── jellycache_settings.example.json  # Example configuration
├── Dockerfile                     # Docker build file
├── docker-compose.yml             # Docker compose config
├── requirements.txt               # Python dependencies
├── plexcache_app.py              # Main application
├── config.py                      # Configuration management
├── jellyfin_api.py               # Jellyfin API integration
├── file_operations.py            # File moving operations
├── logging_config.py             # Logging setup
├── system_utils.py               # System utilities
├── logs/
│   └── plexcache.log             # Application logs (auto-created)
└── plexcache_ondeck_tracker.json # Runtime state (auto-created)
```

> **Note**: The `logs/` folder and `plexcache_ondeck_tracker.json` are created automatically on first run.

## Updating

To update JellyCache-R:

**If you used git clone:**
```bash
cd /mnt/user/appdata/jellycache
git pull
docker compose build --no-cache
docker compose up
```

**If you copied files manually:**
```bash
cd /mnt/user/appdata/jellycache
# Copy updated files from source (all *.py files, requirements.txt, Dockerfile, docker-compose.yml)
docker compose build --no-cache
docker compose up
```

> **Tip**: Your `jellycache_settings.json` will not be overwritten during updates. Check the example file for any new settings after updating.

## Glossary

| Term | Description |
|------|-------------|
| **Continue Watching** | Jellyfin's list of partially watched items (internally called "ondeck" in code) |
| **Favorites** | Items marked with a heart in Jellyfin |
| **Watchlist** | Alternative name for favorites (legacy compatibility) |
| **plex_path** | Path as seen by Jellyfin inside its container (named for PlexCache-R compatibility) |
| **.plexcached** | Backup extension added to original files when cached |
