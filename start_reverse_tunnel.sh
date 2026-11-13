#!/bin/bash
# Start and maintain persistent SSH reverse tunnel from local server to DreamHost
# This creates a tunnel so DreamHost can SSH back to local server for syncing
# Run on: Local server (ethel@192.168.2.10)
# Usage: ./start_reverse_tunnel.sh
# For cron: Add to local crontab: */5 * * * * /home/ethel/recipes_remote/start_reverse_tunnel.sh >/dev/null 2>&1

# Configuration
DREAMHOST_USER="f42widec"
DREAMHOST_HOST="pdx1-shared-a3-07.dreamhost.com"
DREAMHOST_KEY="/home/ethel/.ssh/id_rsa_dreamhost"

TUNNEL_PORT="2222"  # Port on DreamHost that connects back to local SSH (22)
LOCAL_SSH_PORT="22"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TUNNEL_PID_FILE="$SCRIPT_DIR/.tunnel.pid"
LOG_FILE="$SCRIPT_DIR/tunnel.log"

# Function to log
log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to check if tunnel is alive
tunnel_is_alive() {
    if [ ! -f "$TUNNEL_PID_FILE" ]; then
        return 1
    fi
    
    local pid=$(cat "$TUNNEL_PID_FILE" 2>/dev/null)
    if [ -z "$pid" ]; then
        return 1
    fi
    
    if ps -p "$pid" > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Function to start tunnel
start_tunnel() {
    log_msg "Starting SSH reverse tunnel to DreamHost..."
    
    # Remove old PID file if it exists
    rm -f "$TUNNEL_PID_FILE"
    
    # Start reverse tunnel in background
    # -R 2222:localhost:22 = DreamHost port 2222 connects to local port 22
    # -N = Don't execute remote command (just tunnel)
    # -f = Fork to background
    # -o ServerAliveInterval=60 = Keep alive by sending heartbeat every 60 sec
    # -o ServerAliveCountMax=3 = Disconnect after 3 missed heartbeats (180 sec)
    
    ssh -i "$DREAMHOST_KEY" \
        -R "$TUNNEL_PORT:localhost:$LOCAL_SSH_PORT" \
        -N -f \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o ConnectTimeout=10 \
        "$DREAMHOST_USER@$DREAMHOST_HOST" 2>/dev/null
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        # Get the SSH process PID (most recent background SSH process for this host)
        local ssh_pid=$(pgrep -f "ssh.*-R.*$TUNNEL_PORT.*$DREAMHOST_HOST" | tail -1)
        
        if [ ! -z "$ssh_pid" ]; then
            echo "$ssh_pid" > "$TUNNEL_PID_FILE"
            log_msg "✓ Tunnel started successfully (PID: $ssh_pid)"
            echo "✓ Tunnel active"
            return 0
        else
            log_msg "✗ Tunnel SSH process started but PID could not be determined"
            return 1
        fi
    else
        log_msg "✗ Failed to start tunnel (exit code: $exit_code)"
        return 1
    fi
}

# Function to stop tunnel
stop_tunnel() {
    log_msg "Stopping SSH reverse tunnel..."
    
    if [ -f "$TUNNEL_PID_FILE" ]; then
        local pid=$(cat "$TUNNEL_PID_FILE")
        if kill "$pid" 2>/dev/null; then
            log_msg "✓ Tunnel stopped (PID: $pid)"
            rm -f "$TUNNEL_PID_FILE"
            return 0
        else
            log_msg "✗ Could not stop tunnel (PID: $pid not found)"
            rm -f "$TUNNEL_PID_FILE"
            return 1
        fi
    else
        log_msg "No tunnel PID file found"
        return 1
    fi
}

# Main logic
case "${1:-status}" in
    start)
        if tunnel_is_alive; then
            log_msg "Tunnel already running"
            echo "✓ Tunnel already running"
        else
            start_tunnel
        fi
        ;;
    stop)
        stop_tunnel
        ;;
    restart)
        stop_tunnel
        sleep 2
        start_tunnel
        ;;
    status)
        if tunnel_is_alive; then
            local pid=$(cat "$TUNNEL_PID_FILE" 2>/dev/null)
            echo "✓ Tunnel is active (PID: $pid)"
            log_msg "Status check: Tunnel is active"
            exit 0
        else
            echo "✗ Tunnel is NOT active"
            log_msg "Status check: Tunnel is NOT active"
            exit 1
        fi
        ;;
    check|healthcheck)
        # Used by cron to keep tunnel alive
        if tunnel_is_alive; then
            exit 0
        else
            log_msg "Tunnel health check failed, restarting..."
            start_tunnel
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|check|healthcheck}"
        exit 1
        ;;
esac

exit 0
