#!/bin/bash
# Backup recipes database to timestamped file
# Usage: ./backup_recipes.sh
# Add to crontab for daily backups: 0 2 * * * /home/f42widec/recipes_remote/backup_recipes.sh

RECIPES_DIR="/home/f42widec/recipes_remote"
DB_FILE="$RECIPES_DIR/recipes.db"
BACKUP_DIR="$RECIPES_DIR/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/recipes.db.backup_$TIMESTAMP"
LOG_FILE="$RECIPES_DIR/backup.log"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Function to log messages
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    log_msg "ERROR: Database file not found at $DB_FILE"
    exit 1
fi

# Create backup copy
if cp "$DB_FILE" "$BACKUP_FILE"; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_msg "Backup created: $BACKUP_FILE ($SIZE)"
    
    # Keep only last 30 backups (delete older ones)
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/recipes.db.backup_* 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 30 ]; then
        OLDEST=$(ls -1t "$BACKUP_DIR"/recipes.db.backup_* | tail -1)
        rm "$OLDEST"
        log_msg "Removed old backup: $OLDEST (kept 30 most recent)"
    fi
    
    # Also create a "latest" symlink for quick access
    ln -sf "$BACKUP_FILE" "$BACKUP_DIR/recipes.db.latest"
    log_msg "Latest backup link updated"
else
    log_msg "ERROR: Failed to create backup"
    exit 1
fi

log_msg "Backup complete. Total backups: $BACKUP_COUNT"
