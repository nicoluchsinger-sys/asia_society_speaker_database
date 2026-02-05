#!/bin/bash

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="speakers_${DATE}.db"

mkdir -p "$BACKUP_DIR"

# Create backup
cp speakers.db "$BACKUP_DIR/$FILENAME"

# Compress
gzip "$BACKUP_DIR/$FILENAME"

# Keep only last 30 days
find "$BACKUP_DIR" -name "speakers_*.db.gz" -mtime +30 -delete

echo "Backup created: $FILENAME.gz"

# Print backup size
du -h "$BACKUP_DIR/$FILENAME.gz"
