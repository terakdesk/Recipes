#!/bin/bash
# Reverse sync: Push recipes from production (DreamHost) to local server (ethel@192.168.2.10)
# This script runs ON the production server and pushes data to local
# Production (DreamHost) is master, local (192.168.2.10) is replica
# Usage: ./sync_production_to_local.sh
# Add to DreamHost crontab: 0 3 * * * /home/f42widec/recipes_remote/sync_production_to_local.sh

# Configuration
PRODUCTION_APP_DIR="/home/f42widec/recipes_remote"

LOCAL_USER="ethel"
LOCAL_HOST="192.168.2.10"
LOCAL_APP_DIR="/home/ethel/recipes_remote"

# SSH Configuration
SSH_KEY="/home/f42widec/.ssh/id_rsa_local"
SSH_OPTIONS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -i $SSH_KEY"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$SCRIPT_DIR/sync.log"

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
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}✓ $1${NC}" | tee -a "$LOG_FILE"
}

log_msg "================================================"
log_msg "Starting one-way sync: Production → Local"
log_msg "Production (here): $PRODUCTION_APP_DIR"
log_msg "Local (remote): $LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR"
log_msg "================================================"

# Step 1: Check local database exists
log_msg "Step 1: Checking local database..."
if [ ! -f "$PRODUCTION_APP_DIR/recipes.db" ]; then
    log_error "Production database not found: $PRODUCTION_APP_DIR/recipes.db"
    exit 1
fi
log_success "Local database exists"

# Step 2: Check connectivity to local server
log_msg "Step 2: Checking connectivity to local server..."
if ! ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "test -d $LOCAL_APP_DIR" 2>/dev/null; then
    log_error "Cannot connect to local server or directory not found"
    log_error "SSH Key: $SSH_KEY"
    log_error "Target: $LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR"
    exit 1
fi
log_success "Connected to local server"

# Step 3: Create backup on local server
log_msg "Step 3: Creating backup on local server..."
BACKUP_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DB="$LOCAL_APP_DIR/sync_backups/recipes.db.backup_$BACKUP_TIMESTAMP"

if ! ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "mkdir -p $LOCAL_APP_DIR/sync_backups && cp $LOCAL_APP_DIR/recipes.db '$BACKUP_DB'" 2>/dev/null; then
    log_error "Failed to create backup on local server"
    exit 1
fi
log_success "Backup created on local server: $BACKUP_DB"

# Step 4: Push database to local server
log_msg "Step 4: Pushing database to local server..."
if ! scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no -i $SSH_KEY "$PRODUCTION_APP_DIR/recipes.db" "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/recipes.db" 2>/dev/null; then
    log_error "Failed to push database to local server"
    exit 1
fi
log_success "Database pushed to local server"

# Step 5: Push saved_recipes_json directory
log_msg "Step 5: Pushing saved_recipes_json directory..."

# Backup local JSON on remote server first
log_msg "  Backing up local JSON directory..."
BACKUP_JSON="$LOCAL_APP_DIR/sync_backups/saved_recipes_json.backup_$BACKUP_TIMESTAMP"
if ! ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "mkdir -p $LOCAL_APP_DIR/sync_backups && [ -d $LOCAL_APP_DIR/saved_recipes_json ] && cp -r $LOCAL_APP_DIR/saved_recipes_json '$BACKUP_JSON' || true" 2>/dev/null; then
    log_error "Failed to backup JSON directory on local server"
    exit 1
fi
log_success "Local JSON backup created"

# Push JSON directory
log_msg "  Pushing JSON directory..."
if ! scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no -i $SSH_KEY -r "$PRODUCTION_APP_DIR/saved_recipes_json" "$LOCAL_USER@$LOCAL_HOST:$LOCAL_APP_DIR/" 2>/dev/null; then
    log_error "Failed to push JSON directory"
    exit 1
fi
log_success "JSON directory pushed to local server"

# Step 6: Restart Flask on local server
log_msg "Step 6: Restarting Flask on local server..."
if ssh $SSH_OPTIONS "$LOCAL_USER@$LOCAL_HOST" "cd $LOCAL_APP_DIR && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &" 2>/dev/null; then
    log_success "Flask restarted on local server"
else
    log_msg "Note: Could not restart Flask automatically"
fi

# Step 7: Log summary
log_msg "================================================"
log_success "One-way sync completed successfully!"
log_msg "Production → Local sync finished at $(date)"
log_msg "================================================"

exit 0
