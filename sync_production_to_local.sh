#!/bin/bash
# One-way sync: Pull recipes from production (DreamHost) to local server (ethel@192.168.2.10)
# Production is master, local is replica
# Usage: ./sync_production_to_local.sh
# Add to crontab for daily sync: 0 3 * * * /path/to/sync_production_to_local.sh

# Configuration
PRODUCTION_USER="f42widec"
PRODUCTION_HOST="pdx1-shared-a3-07.dreamhost.com"
PRODUCTION_APP_DIR="/home/f42widec/recipes_remote"

LOCAL_USER="ethel"
LOCAL_HOST="192.168.2.10"
LOCAL_APP_DIR="/home/ethel/recipes_remote"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$SCRIPT_DIR/sync.log"
BACKUP_DIR="$SCRIPT_DIR/sync_backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log messages
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to log errors
log_error() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

# Function to log success
log_success() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log_msg "================================================"
log_msg "Starting one-way sync: Production → Local"
log_msg "Production: $PRODUCTION_USER@$PRODUCTION_HOST:$PRODUCTION_APP_DIR"
log_msg "Local: $LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR"
log_msg "================================================"

# Step 1: Check connectivity to production server
log_msg "Step 1: Checking connectivity to production server..."
SSH_KEY="$HOME/.ssh/id_rsa"
SSH_OPTIONS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no"
if [ -f "$SSH_KEY" ]; then
    SSH_OPTIONS="$SSH_OPTIONS -i $SSH_KEY"
fi
if ! ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "test -f $PRODUCTION_APP_DIR/recipes.db" 2>/dev/null; then
    log_error "Cannot connect to production server or recipes.db not found"
    exit 1
fi
log_success "Connected to production server"

# Step 2: Check connectivity to local server
log_msg "Step 2: Checking connectivity to local server..."
if ! ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "test -f $LOCAL_APP_DIR/recipes.db" 2>/dev/null; then
    log_error "Cannot connect to local server or recipes.db not found"
    exit 1
fi
log_success "Connected to local server"

# Step 3: Download production database to temp location on production server
log_msg "Step 3: Preparing database for download from production..."
PRODUCTION_DB_TEMP="/tmp/recipes.db.sync_$$"
if ! ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "cp $PRODUCTION_APP_DIR/recipes.db $PRODUCTION_DB_TEMP && chmod 644 $PRODUCTION_DB_TEMP" 2>/dev/null; then
    log_error "Failed to prepare database on production server"
    exit 1
fi
log_success "Database prepared on production server"

# Step 4: Download database from production to local machine
log_msg "Step 4: Downloading database from production..."
TEMP_LOCAL_DB="/tmp/recipes.db.from_prod_$$"
SCP_CMD="scp"
if [ -f "$SSH_KEY" ]; then
    SCP_CMD="scp -i $SSH_KEY -o StrictHostKeyChecking=no"
fi
if ! $SCP_CMD "$PRODUCTION_USER@$PRODUCTION_HOST:$PRODUCTION_DB_TEMP" "$TEMP_LOCAL_DB" 2>/dev/null; then
    log_error "Failed to download database from production"
    ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
    exit 1
fi
log_success "Database downloaded from production"

# Step 5: Get file sizes for comparison
PROD_DB_SIZE=$(stat -f%z "$TEMP_LOCAL_DB" 2>/dev/null || stat -c%s "$TEMP_LOCAL_DB" 2>/dev/null || echo "unknown")
log_msg "Production database size: $PROD_DB_SIZE bytes"

# Step 6: Backup current local database
log_msg "Step 6: Backing up current local database..."
BACKUP_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DB="$BACKUP_DIR/recipes.db.backup_$BACKUP_TIMESTAMP"

if ! $SCP_CMD "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/recipes.db" "$BACKUP_DB" 2>/dev/null; then
    log_error "Failed to backup local database"
    rm -f "$TEMP_LOCAL_DB"
    ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
    exit 1
fi
log_success "Local database backed up to: $BACKUP_DB"

# Step 7: Copy new database to local server
log_msg "Step 7: Uploading new database to local server..."
if ! $SCP_CMD "$TEMP_LOCAL_DB" "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/recipes.db" 2>/dev/null; then
    log_error "Failed to upload database to local server"
    rm -f "$TEMP_LOCAL_DB"
    ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
    exit 1
fi
log_success "Database uploaded to local server"

# Step 8: Sync saved_recipes_json directory
log_msg "Step 8: Syncing saved_recipes_json directory..."
BACKUP_JSON="$BACKUP_DIR/saved_recipes_json.backup_$BACKUP_TIMESTAMP"

# Backup local JSON directory
log_msg "  Backing up local JSON directory..."
if ! $SCP_CMD -r "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/saved_recipes_json" "$BACKUP_JSON" 2>/dev/null; then
    log_error "Failed to backup local JSON directory"
    rm -f "$TEMP_LOCAL_DB"
    ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
    exit 1
fi
log_success "Local JSON directory backed up"

# Sync JSON directory from production to local (one-way)
log_msg "  Syncing JSON directory from production..."
if ! ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "rsync -av --delete -e 'ssh -i /home/ethel/.ssh/id_rsa -o StrictHostKeyChecking=no' $PRODUCTION_USER@$PRODUCTION_HOST:$PRODUCTION_APP_DIR/saved_recipes_json/ $LOCAL_APP_DIR/saved_recipes_json/" 2>/dev/null; then
    log_msg "Note: rsync not available on local server, using scp..."
    # Fallback to scp if rsync not available
    if ! $SCP_CMD -r "$PRODUCTION_USER@$PRODUCTION_HOST:$PRODUCTION_APP_DIR/saved_recipes_json/*" "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/saved_recipes_json/" 2>/dev/null; then
        log_error "Failed to sync JSON directory"
        rm -f "$TEMP_LOCAL_DB"
        ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
        exit 1
    fi
fi
log_success "JSON directory synced from production"

# Step 9: Restart Flask on local server to pick up database changes
log_msg "Step 9: Restarting Flask on local server..."
if ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "cd $LOCAL_APP_DIR && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &" 2>/dev/null; then
    log_success "Flask restarted on local server"
else
    log_msg "Note: Could not restart Flask automatically, you may need to restart manually"
fi

# Step 10: Cleanup temp files
log_msg "Step 10: Cleaning up temporary files..."
rm -f "$TEMP_LOCAL_DB"
ssh $SSH_OPTIONS "$PRODUCTION_USER@$PRODUCTION_HOST" "rm -f $PRODUCTION_DB_TEMP" 2>/dev/null
log_success "Temporary files cleaned up"

# Step 11: Log summary
log_msg "================================================"
log_success "One-way sync completed successfully!"
log_msg "Production → Local sync finished at $(date)"
log_msg "Backup saved to: $BACKUP_DB"
log_msg "================================================"

exit 0
