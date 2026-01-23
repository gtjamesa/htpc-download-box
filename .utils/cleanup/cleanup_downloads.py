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
import subprocess
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional, env vars can be set manually
    pass

try:
    from tqdm import tqdm
except ImportError:
    # tqdm is optional, provide a simple passthrough
    def tqdm(iterable, **kwargs):
        return iterable


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


def install_cron(script_path: str, args_list: List[str]) -> None:
    """Install script to crontab for weekly execution"""
    # Build the cron command
    script_abs = os.path.abspath(script_path)
    # Filter out --install-cron and --uninstall-cron from args
    filtered_args = [arg for arg in args_list if arg not in ['--install-cron', '--uninstall-cron']]
    cmd = f"{script_abs} {' '.join(filtered_args)}"

    # Cron entry: Run every Sunday at 3 AM
    cron_entry = f"0 3 * * 0 {cmd}"
    cron_marker = f"# qbittorrent-cleanup: {script_abs}"

    try:
        # Get current crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        current_cron = result.stdout if result.returncode == 0 else ""

        # Check if already installed
        if cron_marker in current_cron:
            print("Cron job already installed. Updating...")
            # Remove old entry
            lines = [line for line in current_cron.split('\n')
                    if not (cron_marker in line or (line.startswith('0 3 * * 0') and script_abs in line))]
            current_cron = '\n'.join(lines).strip()

        # Add new entry
        new_cron = f"{current_cron}\n{cron_marker}\n{cron_entry}\n" if current_cron else f"{cron_marker}\n{cron_entry}\n"

        # Install new crontab
        subprocess.run(['crontab', '-'], input=new_cron, text=True, check=True)

        print("=" * 80)
        print("Cron job installed successfully!")
        print("=" * 80)
        print(f"Schedule: Every Sunday at 3:00 AM")
        print(f"Command: {cmd}")
        print()
        print("To view crontab: crontab -l")
        print("To remove: crontab -e (then delete the lines)")
        print(f"Or run: {script_abs} --uninstall-cron")
        print("=" * 80)

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install cron job: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: crontab command not found. Is cron installed?")
        sys.exit(1)


def uninstall_cron(script_path: str) -> None:
    """Remove script from crontab"""
    script_abs = os.path.abspath(script_path)
    cron_marker = f"# qbittorrent-cleanup: {script_abs}"

    try:
        # Get current crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if result.returncode != 0:
            print("No crontab found or crontab is empty.")
            return

        current_cron = result.stdout

        # Check if installed
        if cron_marker not in current_cron:
            print("Cron job not found in crontab.")
            return

        # Remove entries
        lines = [line for line in current_cron.split('\n')
                if not (cron_marker in line or (line.startswith('0 3 * * 0') and script_abs in line))]
        new_cron = '\n'.join(lines).strip() + '\n' if lines else ''

        # Install new crontab
        if new_cron.strip():
            subprocess.run(['crontab', '-'], input=new_cron, text=True, check=True)
        else:
            # Empty crontab, remove it
            subprocess.run(['crontab', '-r'], check=True)

        print("=" * 80)
        print("Cron job uninstalled successfully!")
        print("=" * 80)

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to uninstall cron job: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: crontab command not found. Is cron installed?")
        sys.exit(1)


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


def check_arr_imported(app_name: str, url: str, api_key: str, directory_name: str) -> Tuple[bool, str]:
    """
    Check if directory has been imported by Sonarr/Radarr.
    Returns (imported, reason) tuple.
    """
    try:
        # Check history for successful imports
        response = requests.get(
            f"{url}/api/v3/history",
            headers={'X-Api-Key': api_key},
            params={'pageSize': 1000, 'eventType': 3},  # eventType 3 = downloadFolderImported
            timeout=10
        )

        if response.status_code != 200:
            return (False, f"Failed to query {app_name} API")

        history = response.json()
        records = history.get('records', [])

        # Check if any record matches our directory
        for record in records:
            download_id = record.get('downloadId', '')
            source_path = record.get('data', {}).get('droppedPath', '')

            if directory_name in source_path or directory_name in download_id:
                return (True, f"Imported by {app_name}")

        return (False, f"Not found in {app_name} import history")

    except Exception as e:
        return (False, f"Error checking {app_name}: {e}")


def verify_import_status(
    directory_name: str,
    sonarr_enabled: bool,
    sonarr_url: str,
    sonarr_api_key: str,
    radarr_enabled: bool,
    radarr_url: str,
    radarr_api_key: str
) -> Tuple[bool, str]:
    """
    Check if directory has been imported by Sonarr or Radarr.
    Returns (imported, reason) tuple.
    """
    imported = False
    reason = "Not checked"

    if sonarr_enabled:
        imported, reason = check_arr_imported('Sonarr', sonarr_url, sonarr_api_key, directory_name)

    if not imported and radarr_enabled:
        imported, reason = check_arr_imported('Radarr', radarr_url, radarr_api_key, directory_name)

    return imported, reason


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
  %(prog)s --install-cron --verify-import      # Install to crontab (weekly, Sundays 3 AM)
  %(prog)s --uninstall-cron                    # Remove from crontab
        '''
    )
    parser.add_argument('--host', default=os.getenv('QBITTORRENT_HOST', 'http://localhost:8112'),
                        help='qBittorrent host (default: $QBITTORRENT_HOST or http://localhost:8112)')
    parser.add_argument('--username', default=os.getenv('QBITTORRENT_USERNAME', 'admin'),
                        help='qBittorrent username (default: $QBITTORRENT_USERNAME or admin)')
    parser.add_argument('--password', default=os.getenv('QBITTORRENT_PASSWORD', ''),
                        help='qBittorrent password (default: $QBITTORRENT_PASSWORD or empty)')
    parser.add_argument('--downloads-path', default=os.getenv('DOWNLOADS_PATH', '/downloads/complete'),
                        help='Downloads directory path (default: $DOWNLOADS_PATH or /downloads/complete)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show statistics only, do not delete anything')

    # Sonarr/Radarr verification
    parser.add_argument('--verify-import', action='store_true',
                        help='Verify files have been imported by Sonarr/Radarr before deletion')
    parser.add_argument('--sonarr-url', default=os.getenv('SONARR_URL', 'http://localhost:8989'),
                        help='Sonarr URL (default: $SONARR_URL or http://localhost:8989)')
    parser.add_argument('--sonarr-api-key', default=os.getenv('SONARR_API_KEY', ''),
                        help='Sonarr API key (default: $SONARR_API_KEY)')
    parser.add_argument('--radarr-url', default=os.getenv('RADARR_URL', 'http://localhost:7878'),
                        help='Radarr URL (default: $RADARR_URL or http://localhost:7878)')
    parser.add_argument('--radarr-api-key', default=os.getenv('RADARR_API_KEY', ''),
                        help='Radarr API key (default: $RADARR_API_KEY)')

    # Cron installation
    parser.add_argument('--install-cron', action='store_true',
                        help='Install script to crontab for weekly execution (Sundays at 3 AM)')
    parser.add_argument('--uninstall-cron', action='store_true',
                        help='Remove script from crontab')

    args = parser.parse_args()

    # Handle cron installation/uninstallation
    if args.install_cron:
        install_cron(sys.argv[0], sys.argv[1:])
        return

    if args.uninstall_cron:
        uninstall_cron(sys.argv[0])
        return

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
    extracted_not_imported = []  # Extracted media that hasn't been imported

    total_orphaned_size = 0
    total_not_imported_size = 0
    total_extracted_size = 0
    total_extracted_not_imported_size = 0

    if args.verify_import and (sonarr_enabled or radarr_enabled):
        print("Verifying import status...")
        print()

    for disk_dir in tqdm(disk_directories, desc="Processing directories", unit="dir"):
        dir_name = disk_dir.name

        if dir_name not in qbt_directories:
            # Directory not tracked by qBittorrent
            size = get_dir_size(disk_dir)

            # Check if it's been imported
            if args.verify_import:
                imported, reason = verify_import_status(
                    dir_name, sonarr_enabled, args.sonarr_url, args.sonarr_api_key,
                    radarr_enabled, args.radarr_url, args.radarr_api_key
                )
            else:
                imported = True
                reason = "Not checked"

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
                # Check if directory has been imported (for extracted media verification)
                if args.verify_import:
                    imported, reason = verify_import_status(
                        dir_name, sonarr_enabled, args.sonarr_url, args.sonarr_api_key,
                        radarr_enabled, args.radarr_url, args.radarr_api_key
                    )
                else:
                    imported = True

                if args.verify_import and not imported:
                    # Extracted media from directory that hasn't been imported - skip
                    extracted_not_imported.extend(extracted)
                    total_extracted_not_imported_size += sum(size for _, size in extracted)
                else:
                    # Safe to delete
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
        print(f"Extracted media files (safe to delete): {len(extracted_media)}")
        print(f"Total size: {format_size(total_extracted_size)}")
        print()
        for file_path, size in sorted(extracted_media, key=lambda x: x[1], reverse=True):
            rel_path = file_path.relative_to(downloads_path)
            print(f"  [{format_size(size):>12}] {rel_path}")
        print()
    else:
        print("No extracted media files found (safe to delete).")
        print()

    if args.verify_import and extracted_not_imported:
        print(f"⚠ Extracted media files (NOT IMPORTED - will be skipped): {len(extracted_not_imported)}")
        print(f"Total size: {format_size(total_extracted_not_imported_size)}")
        print()
        for file_path, size in sorted(extracted_not_imported, key=lambda x: x[1], reverse=True):
            rel_path = file_path.relative_to(downloads_path)
            print(f"  [{format_size(size):>12}] {rel_path}")
        print()

    total_size = total_orphaned_size + total_extracted_size
    total_items = len(orphaned_dirs) + len(extracted_media)

    print("=" * 80)
    print(f"TOTAL: {total_items} items, {format_size(total_size)} can be freed")
    if args.verify_import and (orphaned_not_imported or extracted_not_imported):
        skipped_count = len(orphaned_not_imported) + len(extracted_not_imported)
        skipped_size = total_not_imported_size + total_extracted_not_imported_size
        print(f"SKIPPED: {skipped_count} items ({format_size(skipped_size)}) - not imported")
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
