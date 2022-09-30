#!/bin/bash

TIMESTAMP=$(date +"%F")
BACKUP_DIR="/mnt/synology-backups/HtpcDownloadBox"
BACKUP_FILE="$BACKUP_DIR/$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "Starting backup..."

sudo /usr/bin/tar -czvf "$BACKUP_FILE" "$(pwd)/config" "$(pwd)/.env" >/dev/null 2>&1

echo "Backup written to ${BACKUP_FILE}"

# Delete backups older than 7 days
find "$BACKUP_DIR" -type f -mtime +7 -delete

