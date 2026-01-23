# qBittorrent Download Cleanup

Cleans downloads by removing orphaned dirs + extracted media files.

## Setup

```bash
cd .utils/cleanup
bash setup.sh
source venv/bin/activate
```

## Usage

```bash
# Dry run (stats only)
python cleanup_downloads.py --dry-run

# Interactive cleanup
python cleanup_downloads.py

# Verify imports before deletion (recommended)
python cleanup_downloads.py --verify-import --sonarr-api-key YOUR_KEY --radarr-api-key YOUR_KEY

# Custom host/path
python cleanup_downloads.py --host http://localhost:8112 --downloads-path /downloads/complete

# Install to crontab (weekly, Sundays 3 AM)
python cleanup_downloads.py --install-cron --verify-import

# Remove from crontab
python cleanup_downloads.py --uninstall-cron
```

## Options

**qBittorrent:**
- `--host` - qBittorrent API host (or env: QBITTORRENT_HOST, default: http://localhost:8112)
- `--username` - qBittorrent username (or env: QBITTORRENT_USERNAME, default: admin)
- `--password` - qBittorrent password (or env: QBITTORRENT_PASSWORD, default: empty)
- `--downloads-path` - Downloads directory (or env: DOWNLOADS_PATH, default: /downloads/complete)
- `--dry-run` - Show stats only, no deletion

**Import Verification:**
- `--verify-import` - Check Sonarr/Radarr before deleting orphaned dirs
- `--sonarr-url` - Sonarr URL (or env: SONARR_URL, default: http://localhost:8989)
- `--sonarr-api-key` - Sonarr API key (or env: SONARR_API_KEY)
- `--radarr-url` - Radarr URL (or env: RADARR_URL, default: http://localhost:7878)
- `--radarr-api-key` - Radarr API key (or env: RADARR_API_KEY)

**Automation:**
- `--install-cron` - Install to crontab (weekly, Sundays 3 AM)
- `--uninstall-cron` - Remove from crontab

## What it does

1. **Orphaned directories**: Removes dirs not tracked by qBittorrent
2. **Extracted media**: Removes .mkv/.mp4 files extracted from .rar archives (keeps archives)
3. **Import verification** (optional): Checks Sonarr/Radarr history to ensure files were imported before deletion (applies to both orphaned dirs and extracted media)
