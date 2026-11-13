#!/bin/bash
# Sync recipes from production (DreamHost) to local server via SSH reverse tunnel
# This script runs ON DreamHost and syncs via the reverse tunnel
# The local server maintains a persistent SSH tunnel for this to work
# Usage: ./sync_via_tunnel.sh
# Add to DreamHost crontab: 0 3 * * * /home/f42widec/recipes_remote/sync_via_tunnel.sh >> /home/f42widec/recipes_remote/sync_cron.log 2>&1

# Configuration
PRODUCTION_APP_DIR="/home/f42widec/recipes_remote"
TUNNEL_HOST="localhost"
TUNNEL_PORT="2222"
LOCAL_USER="ethel"
LOCAL_APP_DIR="/home/ethel/recipes_remote"

# SSH options for connecting through tunnel
SSH_TUNNEL_OPTIONS="-p $TUNNEL_PORT -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="$SCRIPT_DIR/sync_tunnel.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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
log_msg "Starting sync: Production → Local (via tunnel)"
log_msg "Production (here): $PRODUCTION_APP_DIR"
log_msg "Local (via tunnel): $LOCAL_USER@$TUNNEL_HOST:$TUNNEL_PORT:$LOCAL_APP_DIR"
log_msg "================================================"

# Step 1: Verify production database exists
log_msg "Step 1: Verifying production database..."
if [ ! -f "$PRODUCTION_APP_DIR/recipes.db" ]; then
    log_error "Production database not found: $PRODUCTION_APP_DIR/recipes.db"
    exit 1
fi
log_success "Production database exists"

# Step 2: Test tunnel connectivity
log_msg "Step 2: Testing SSH tunnel connectivity..."
if ! ssh $SSH_TUNNEL_OPTIONS "$LOCAL_USER@$TUNNEL_HOST" "test -d $LOCAL_APP_DIR" 2>/dev/null; then
    log_error "Cannot connect to local server via tunnel"
    log_error "Tunnel: $TUNNEL_HOST:$TUNNEL_PORT"
    log_error "Target directory: $LOCAL_APP_DIR"
    exit 1
fi
log_success "Tunnel connection successful"

# Step 3: Create backup on local server
log_msg "Step 3: Creating backup on local server..."
BACKUP_TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DB="$LOCAL_APP_DIR/sync_backups/recipes.db.backup_$BACKUP_TIMESTAMP"

if ! ssh $SSH_TUNNEL_OPTIONS "$LOCAL_USER@$TUNNEL_HOST" "mkdir -p $LOCAL_APP_DIR/sync_backups && cp $LOCAL_APP_DIR/recipes.db '$BACKUP_DB'" 2>/dev/null; then
    log_error "Failed to create backup on local server"
    exit 1
fi
log_success "Backup created: $BACKUP_DB"

# Step 4: Sync database via SCP
log_msg "Step 4: Syncing recipes.db via tunnel..."
if ! scp -P "$TUNNEL_PORT" \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PRODUCTION_APP_DIR/recipes.db" \
    "$LOCAL_USER@$TUNNEL_HOST:$LOCAL_APP_DIR/recipes.db" 2>/dev/null; then
    log_error "Failed to sync recipes.db"
    exit 1
fi
log_success "Database synced successfully"

# Step 5: Backup and sync JSON directory
log_msg "Step 5: Syncing saved_recipes_json/ directory..."

# First backup existing JSON
log_msg "  Backing up local JSON directory..."
BACKUP_JSON="$LOCAL_APP_DIR/sync_backups/saved_recipes_json.backup_$BACKUP_TIMESTAMP"
if ! ssh $SSH_TUNNEL_OPTIONS "$LOCAL_USER@$TUNNEL_HOST" \
    "mkdir -p $LOCAL_APP_DIR/sync_backups && [ -d $LOCAL_APP_DIR/saved_recipes_json ] && cp -r $LOCAL_APP_DIR/saved_recipes_json '$BACKUP_JSON' || true" 2>/dev/null; then
    log_error "Failed to backup JSON directory"
    exit 1
fi
log_success "JSON backup created"

# Then sync JSON directory
log_msg "  Syncing JSON files..."
if ! scp -P "$TUNNEL_PORT" \
    -r \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "$PRODUCTION_APP_DIR/saved_recipes_json" \
    "$LOCAL_USER@$TUNNEL_HOST:$LOCAL_APP_DIR/" 2>/dev/null; then
    log_error "Failed to sync JSON directory"
    exit 1
fi
log_success "JSON directory synced"

# Step 6: Restart Flask on local server
log_msg "Step 6: Restarting Flask on local server..."
if ssh $SSH_TUNNEL_OPTIONS "$LOCAL_USER@$TUNNEL_HOST" \
    "cd $LOCAL_APP_DIR && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &" 2>/dev/null; then
    log_success "Flask restarted"
else
    log_msg "Note: Could not restart Flask automatically (non-critical)"
fi

# Step 7: Log summary
log_msg "================================================"
log_success "Sync completed successfully!"
log_msg "Production → Local sync finished at $(date)"
log_msg "================================================"

exit 0
