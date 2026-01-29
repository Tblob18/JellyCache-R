# JellyCache-R Unraid Deployment Guide

This guide walks you through deploying JellyCache-R on Unraid to automatically cache actively watched media on your SSD.

## Prerequisites

- Unraid server with Docker support
- Jellyfin running (with API key)
- SSD cache drive configured
- SSH or terminal access to Unraid

## Quick Start

### 1. Create the appdata directory

```bash
mkdir -p /mnt/user/appdata/jellycache/logs
```

### 2. Copy configuration file

Copy `jellycache_settings.example.json` to your Unraid server and customize it:

```bash
# From your local machine (adjust paths as needed)
scp jellycache_settings.example.json root@YOUR_UNRAID_IP:/mnt/user/appdata/jellycache/jellycache_settings.json
```

Then edit the file and replace:
- `YOUR_JELLYFIN_IP` with your Jellyfin server IP
- `YOUR_JELLYFIN_API_KEY` with your API key (Dashboard > API Keys)
- `YOUR_SHARE` with your Unraid share name (e.g., `Vault`)

### 3. Copy Docker files

```bash
# Copy the entire repo or just these files:
scp Dockerfile docker-compose.yml root@YOUR_UNRAID_IP:/mnt/user/appdata/jellycache/
```

### 4. Verify your path mappings

Edit `/mnt/user/appdata/jellycache/jellycache_settings.json` and ensure:

- `plex_path` matches what Jellyfin sees inside its container (check Jellyfin > Dashboard > Libraries)
- `real_path` is the actual array path (`/mnt/user/...`)
- `cache_path` is the cache equivalent (`/mnt/cache/...`)

Example for German folder names:
```json
"path_mappings": [
    {
        "name": "TV Shows",
        "plex_path": "/data/tvshows/",
        "real_path": "/mnt/user/Vault/Media/Serien/",
        "cache_path": "/mnt/cache/Vault/Media/Serien/"
    },
    {
        "name": "Movies",
        "plex_path": "/data/movies/",
        "real_path": "/mnt/user/Vault/Media/Filme/",
        "cache_path": "/mnt/cache/Vault/Media/Filme/"
    }
]
```

### 5. Test with dry-run

```bash
cd /mnt/user/appdata/jellycache

# Edit docker-compose.yml to enable dry-run (uncomment the command line)
# Or run directly:
docker-compose run --rm jellycache python plexcache_app.py --config /config/jellycache_settings.json --dry-run --verbose
```

### 6. Run for real

Once dry-run looks good:

```bash
docker-compose up --build
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
docker-compose up --build 2>&1
```

### Option B: Cron

Add to `/boot/config/go` (persists across reboots):

```bash
# Run every 6 hours
echo "0 */6 * * * cd /mnt/user/appdata/jellycache && docker-compose up --build >> /mnt/user/appdata/jellycache/logs/cron.log 2>&1" >> /var/spool/cron/crontabs/root
```

## Configuration Reference

| Setting | Description | Recommended |
|---------|-------------|-------------|
| `days_to_monitor` | How far back to look at watch history | 7 days |
| `cache_retention_hours` | How long to keep items after leaving Continue Watching | 72 (3 days) |
| `favorites_retention_days` | How long to keep favorited items | 7 days |
| `number_episodes` | Episodes to cache ahead for TV shows | 5 |
| `hardlinked_files` | How to handle seeding torrents | "skip" (safe) |

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

```
/mnt/user/appdata/jellycache/
├── jellycache_settings.json    # Your configuration
├── Dockerfile                   # Docker build file
├── docker-compose.yml          # Docker compose config
├── logs/
│   └── plexcache.log           # Application logs
└── plexcache_ondeck_tracker.json  # Runtime state (auto-created)
```

## Updating

To update JellyCache-R:

```bash
cd /mnt/user/appdata/jellycache
# Pull latest code or copy updated files
docker-compose build --no-cache
docker-compose up
```
