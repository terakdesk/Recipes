#!/bin/bash
# Auto-restart Flask if it crashes
# Add to crontab: */5 * * * * /home/f42widec/recipes_remote/check_and_restart_flask.sh

RECIPES_DIR="/home/f42widec/recipes_remote"
PID_FILE="$RECIPES_DIR/gunicorn.pid"
LOG_FILE="$RECIPES_DIR/restart.log"

# Function to log messages
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check if gunicorn is running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ! ps -p "$PID" > /dev/null 2>&1; then
        log_msg "Flask not running (PID $PID not found). Restarting..."
        cd "$RECIPES_DIR"
        nohup ./start.sh > gunicorn.log 2>&1 &
        NEW_PID=$!
        echo $NEW_PID > "$PID_FILE"
        log_msg "Flask restarted with PID $NEW_PID"
    fi
else
    # No PID file - check if any gunicorn process exists
    if ! pgrep -f "gunicorn.*app:app" > /dev/null 2>&1; then
        log_msg "No Flask instance found. Starting..."
        cd "$RECIPES_DIR"
        nohup ./start.sh > gunicorn.log 2>&1 &
        echo $! > "$PID_FILE"
        log_msg "Flask started with PID $(cat $PID_FILE)"
    fi
fi
