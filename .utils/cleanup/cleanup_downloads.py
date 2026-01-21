#!/usr/bin/env python3
"""
qBittorrent Download Cleanup Script

Cleans up download directories by:
1. Removing directories not tracked by qBittorrent
2. Removing extracted media files when archive files still exist
3. Optionally verifying with Sonarr/Radarr that files have been imported
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import re

try:
    import qbittorrentapi
except ImportError:
    print("ERROR: qbittorrent-api not installed. Install with: pip install qbittorrent-api")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Install with: pip install requests")
    sys.exit(1)


# Media file extensions that may be extracted from archives
MEDIA_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

# Archive file patterns
ARCHIVE_EXTENSIONS = {'.rar', '.zip', '.7z'}
ARCHIVE_PART_PATTERN = re.compile(r'\.r\d+$', re.IGNORECASE)


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_dir_size(path: Path) -> int:
    """Calculate total size of directory"""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total


def get_file_size(path: Path) -> int:
    """Get size of a single file"""
    try:
        return path.stat().st_size
    except (PermissionError, OSError):
        return 0


def is_archive_file(filename: str) -> bool:
    """Check if file is an archive or archive part"""
    lower = filename.lower()
    return (any(lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS) or
            ARCHIVE_PART_PATTERN.search(filename) is not None)


def connect_qbittorrent(host: str, username: str, password: str) -> qbittorrentapi.Client:
    """Connect to qBittorrent API"""
    try:
        client = qbittorrentapi.Client(
            host=host,
            username=username,
            password=password
        )
        client.auth_log_in()
        return client
    except qbittorrentapi.LoginFailed:
        print(f"ERROR: Failed to login to qBittorrent at {host}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to connect to qBittorrent: {e}")
        sys.exit(1)


def check_arr_connection(app_name: str, url: str, api_key: str) -> bool:
    """Check if Sonarr/Radarr is accessible"""
    try:
        response = requests.get(
            f"{url}/api/v3/system/status",
            headers={'X-Api-Key': api_key},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


def check_sonarr_imported(sonarr_url: str, api_key: str, directory_name: str) -> Tuple[bool, str]:
    """
    Check if directory has been imported by Sonarr.
    Returns (imported, reason) tuple.
    """
    try:
        # Check history for successful imports
        response = requests.get(
            f"{sonarr_url}/api/v3/history",
            headers={'X-Api-Key': api_key},
            params={'pageSize': 1000, 'eventType': 3},  # eventType 3 = downloadFolderImported
            timeout=10
        )

        if response.status_code != 200:
            return (False, "Failed to query Sonarr API")

        history = response.json()
        records = history.get('records', [])

        # Check if any record matches our directory
        for record in records:
            download_id = record.get('downloadId', '')
            source_path = record.get('data', {}).get('droppedPath', '')

            if directory_name in source_path or directory_name in download_id:
                return (True, f"Imported by Sonarr")

        return (False, "Not found in Sonarr import history")

    except Exception as e:
        return (False, f"Error checking Sonarr: {e}")


def check_radarr_imported(radarr_url: str, api_key: str, directory_name: str) -> Tuple[bool, str]:
    """
    Check if directory has been imported by Radarr.
    Returns (imported, reason) tuple.
    """
    try:
        # Check history for successful imports
        response = requests.get(
            f"{radarr_url}/api/v3/history",
            headers={'X-Api-Key': api_key},
            params={'pageSize': 1000, 'eventType': 3},  # eventType 3 = downloadFolderImported
            timeout=10
        )

        if response.status_code != 200:
            return (False, "Failed to query Radarr API")

        history = response.json()
        records = history.get('records', [])

        # Check if any record matches our directory
        for record in records:
            download_id = record.get('downloadId', '')
            source_path = record.get('data', {}).get('droppedPath', '')

            if directory_name in source_path or directory_name in download_id:
                return (True, f"Imported by Radarr")

        return (False, "Not found in Radarr import history")

    except Exception as e:
        return (False, f"Error checking Radarr: {e}")


def get_qbt_directories(client: qbittorrentapi.Client) -> Set[str]:
    """Get set of top-level directory names tracked by qBittorrent"""
    directories = set()

    for torrent in client.torrents_info():
        save_path = Path(torrent.save_path)
        content_path = Path(torrent.content_path)

        # Get the directory name relative to save_path
        if content_path.is_relative_to(save_path):
            rel_path = content_path.relative_to(save_path)
            # Get the top-level directory
            top_dir = str(rel_path).split(os.sep)[0]
            directories.add(top_dir)
        else:
            # content_path is the full path including save_path
            directories.add(content_path.name)

    return directories


def get_qbt_torrent_files(client: qbittorrentapi.Client) -> Dict[str, Set[str]]:
    """Get mapping of directory -> set of files tracked by qBittorrent"""
    torrent_files = {}

    for torrent in client.torrents_info():
        save_path = Path(torrent.save_path)
        content_path = Path(torrent.content_path)

        # Get the directory name
        if content_path.is_relative_to(save_path):
            rel_path = content_path.relative_to(save_path)
            top_dir = str(rel_path).split(os.sep)[0]
        else:
            top_dir = content_path.name

        if top_dir not in torrent_files:
            torrent_files[top_dir] = set()

        # Get file list for this torrent
        try:
            files = client.torrents_files(torrent.hash)
            for file in files:
                # Store just the filename (not full path)
                torrent_files[top_dir].add(Path(file.name).name)
        except Exception:
            pass

    return torrent_files


def scan_downloads_directory(downloads_path: Path) -> List[Path]:
    """Scan downloads directory and return list of top-level directories"""
    if not downloads_path.exists():
        print(f"ERROR: Downloads path does not exist: {downloads_path}")
        sys.exit(1)

    directories = []
    try:
        for entry in downloads_path.iterdir():
            if entry.is_dir():
                directories.append(entry)
    except PermissionError:
        print(f"ERROR: Permission denied accessing {downloads_path}")
        sys.exit(1)

    return directories


def find_extracted_media(directory: Path, qbt_files: Set[str]) -> List[Tuple[Path, int]]:
    """
    Find media files that appear to be extracted from archives.
    Returns list of (file_path, size) tuples.
    """
    extracted_files = []

    # Get all files in directory
    all_files = list(directory.rglob('*'))

    # Check if there are archive files
    has_archives = any(is_archive_file(f.name) for f in all_files if f.is_file())

    if not has_archives:
        return extracted_files

    # Find media files
    for file_path in all_files:
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext in MEDIA_EXTENSIONS:
            # Check if this file is tracked by qBittorrent
            if file_path.name not in qbt_files:
                # This is an extracted file (not in the torrent)
                size = get_file_size(file_path)
                extracted_files.append((file_path, size))

    return extracted_files


def main():
    parser = argparse.ArgumentParser(
        description='Clean up qBittorrent download directories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --dry-run                          # Show what would be deleted
  %(prog)s --verify-import                     # Verify imports before cleanup
  %(prog)s --host http://localhost:8112        # Specify qBittorrent host
        '''
    )
    parser.add_argument('--host', default='http://localhost:8112',
                        help='qBittorrent host (default: http://localhost:8112)')
    parser.add_argument('--username', default='admin',
                        help='qBittorrent username (default: admin)')
    parser.add_argument('--password', default='',
                        help='qBittorrent password (default: empty)')
    parser.add_argument('--downloads-path', default='/downloads/complete',
                        help='Downloads directory path (default: /downloads/complete)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show statistics only, do not delete anything')

    # Sonarr/Radarr verification
    parser.add_argument('--verify-import', action='store_true',
                        help='Verify files have been imported by Sonarr/Radarr before deletion')
    parser.add_argument('--sonarr-url', default='http://localhost:8989',
                        help='Sonarr URL (default: http://localhost:8989)')
    parser.add_argument('--sonarr-api-key', default='',
                        help='Sonarr API key')
    parser.add_argument('--radarr-url', default='http://localhost:7878',
                        help='Radarr URL (default: http://localhost:7878)')
    parser.add_argument('--radarr-api-key', default='',
                        help='Radarr API key')

    args = parser.parse_args()

    downloads_path = Path(args.downloads_path)

    print("=" * 80)
    print("qBittorrent Download Cleanup")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'CLEANUP'}")
    print(f"Downloads path: {downloads_path}")
    if args.verify_import:
        print(f"Import verification: ENABLED")
    print()

    # Connect to qBittorrent
    print("Connecting to qBittorrent...")
    client = connect_qbittorrent(args.host, args.username, args.password)
    print(f"✓ Connected to qBittorrent at {args.host}")
    print()

    # Verify Sonarr/Radarr connections if needed
    sonarr_enabled = False
    radarr_enabled = False

    if args.verify_import:
        print("Verifying Sonarr/Radarr connections...")

        if args.sonarr_api_key:
            if check_arr_connection('Sonarr', args.sonarr_url, args.sonarr_api_key):
                print(f"✓ Connected to Sonarr at {args.sonarr_url}")
                sonarr_enabled = True
            else:
                print(f"✗ Failed to connect to Sonarr at {args.sonarr_url}")

        if args.radarr_api_key:
            if check_arr_connection('Radarr', args.radarr_url, args.radarr_api_key):
                print(f"✓ Connected to Radarr at {args.radarr_url}")
                radarr_enabled = True
            else:
                print(f"✗ Failed to connect to Radarr at {args.radarr_url}")

        if not sonarr_enabled and not radarr_enabled:
            print("WARNING: Import verification enabled but no Sonarr/Radarr connections available")
            print("Provide --sonarr-api-key and/or --radarr-api-key")

        print()

    # Get qBittorrent data
    print("Fetching qBittorrent torrent data...")
    qbt_directories = get_qbt_directories(client)
    qbt_torrent_files = get_qbt_torrent_files(client)
    print(f"✓ Found {len(qbt_directories)} directories tracked by qBittorrent")
    print()

    # Scan downloads directory
    print("Scanning downloads directory...")
    disk_directories = scan_downloads_directory(downloads_path)
    print(f"✓ Found {len(disk_directories)} directories on disk")
    print()

    # Find cleanup candidates
    orphaned_dirs = []  # Directories not in qBittorrent
    orphaned_not_imported = []  # Orphaned dirs that haven't been imported
    extracted_media = []  # Extracted media files to remove

    total_orphaned_size = 0
    total_not_imported_size = 0
    total_extracted_size = 0

    if args.verify_import and (sonarr_enabled or radarr_enabled):
        print("Verifying import status...")
        print()

    for disk_dir in disk_directories:
        dir_name = disk_dir.name

        if dir_name not in qbt_directories:
            # Directory not tracked by qBittorrent
            size = get_dir_size(disk_dir)

            # Check if it's been imported
            imported = False
            reason = "Not checked"

            if args.verify_import:
                if sonarr_enabled:
                    imported, reason = check_sonarr_imported(
                        args.sonarr_url, args.sonarr_api_key, dir_name
                    )

                if not imported and radarr_enabled:
                    imported, reason = check_radarr_imported(
                        args.radarr_url, args.radarr_api_key, dir_name
                    )

            if args.verify_import and not imported:
                orphaned_not_imported.append((disk_dir, size, reason))
                total_not_imported_size += size
            else:
                orphaned_dirs.append((disk_dir, size, reason if args.verify_import else ""))
                total_orphaned_size += size
        else:
            # Directory is tracked, check for extracted media
            qbt_files = qbt_torrent_files.get(dir_name, set())
            extracted = find_extracted_media(disk_dir, qbt_files)
            if extracted:
                extracted_media.extend(extracted)
                total_extracted_size += sum(size for _, size in extracted)

    # Display statistics
    print("=" * 80)
    print("CLEANUP SUMMARY")
    print("=" * 80)
    print()

    if orphaned_dirs:
        print(f"Orphaned directories (safe to delete): {len(orphaned_dirs)}")
        print(f"Total size: {format_size(total_orphaned_size)}")
        print()
        for dir_path, size, reason in sorted(orphaned_dirs, key=lambda x: x[1], reverse=True):
            reason_str = f" - {reason}" if reason else ""
            print(f"  [{format_size(size):>12}] {dir_path.name}{reason_str}")
        print()
    else:
        print("No orphaned directories found (safe to delete).")
        print()

    if args.verify_import and orphaned_not_imported:
        print(f"⚠ Orphaned directories (NOT IMPORTED - will be skipped): {len(orphaned_not_imported)}")
        print(f"Total size: {format_size(total_not_imported_size)}")
        print()
        for dir_path, size, reason in sorted(orphaned_not_imported, key=lambda x: x[1], reverse=True):
            print(f"  [{format_size(size):>12}] {dir_path.name} - {reason}")
        print()

    if extracted_media:
        print(f"Extracted media files: {len(extracted_media)}")
        print(f"Total size: {format_size(total_extracted_size)}")
        print()
        for file_path, size in sorted(extracted_media, key=lambda x: x[1], reverse=True):
            rel_path = file_path.relative_to(downloads_path)
            print(f"  [{format_size(size):>12}] {rel_path}")
        print()
    else:
        print("No extracted media files found.")
        print()

    total_size = total_orphaned_size + total_extracted_size
    total_items = len(orphaned_dirs) + len(extracted_media)

    print("=" * 80)
    print(f"TOTAL: {total_items} items, {format_size(total_size)} can be freed")
    if args.verify_import and orphaned_not_imported:
        print(f"SKIPPED: {len(orphaned_not_imported)} items ({format_size(total_not_imported_size)}) - not imported")
    print("=" * 80)
    print()

    if args.dry_run:
        print("DRY RUN - No files were deleted")
        return

    if total_items == 0:
        print("Nothing to clean up!")
        return

    # Prompt for confirmation
    print("WARNING: This will permanently delete the files/directories listed above.")
    response = input("Do you want to proceed? [y/N]: ").strip().lower()

    if response != 'y':
        print("Cleanup cancelled.")
        return

    print()
    print("Starting cleanup...")
    print()

    # Delete orphaned directories
    deleted_dirs = 0
    for dir_path, size, _ in orphaned_dirs:
        try:
            import shutil
            shutil.rmtree(dir_path)
            print(f"✓ Deleted directory: {dir_path.name} ({format_size(size)})")
            deleted_dirs += 1
        except Exception as e:
            print(f"✗ Failed to delete {dir_path.name}: {e}")

    # Delete extracted media files
    deleted_files = 0
    for file_path, size in extracted_media:
        try:
            file_path.unlink()
            rel_path = file_path.relative_to(downloads_path)
            print(f"✓ Deleted file: {rel_path} ({format_size(size)})")
            deleted_files += 1
        except Exception as e:
            print(f"✗ Failed to delete {file_path}: {e}")

    print()
    print("=" * 80)
    print(f"Cleanup complete: {deleted_dirs} directories, {deleted_files} files deleted")
    print(f"Space freed: {format_size(total_size)}")
    print("=" * 80)


if __name__ == '__main__':
    main()
