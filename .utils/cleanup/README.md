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

# Custom host/path
python cleanup_downloads.py --host http://localhost:8112 --downloads-path /downloads/complete
```

## Options

- `--host` - qBittorrent API host (default: http://localhost:8112)
- `--username` - qBittorrent username (default: admin)
- `--password` - qBittorrent password (default: empty)
- `--downloads-path` - Downloads directory (default: /downloads/complete)
- `--dry-run` - Show stats only, no deletion

## What it does

1. **Orphaned directories**: Removes dirs not tracked by qBittorrent
2. **Extracted media**: Removes .mkv/.mp4 files extracted from .rar archives (keeps archives)
