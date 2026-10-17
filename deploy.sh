#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy.sh [user@host] [remote_dir]
HOST=${1:-me@192.168.2.170}
REMOTE_DIR=${2:-~/recipes_remote}

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Copying app.py and templates/ to $HOST:$REMOTE_DIR"
scp "$REPO_DIR/app.py" "$HOST:$REMOTE_DIR/"
scp -r "$REPO_DIR/templates" "$HOST:$REMOTE_DIR/"

echo "Restarting recipes.service on $HOST and showing recent journal lines"
ssh "$HOST" 'sudo systemctl restart recipes.service && sudo journalctl -u recipes.service -n 80 --no-pager'

echo "Checking unix socket response (may fail if service not ready)"
ssh "$HOST" 'curl -v --unix-socket /run/recipes/recipes.sock http://localhost/ -I || true'

echo "Done. If the site still doesn't show updated content, clear browser cache or try fetching the index directly on the server."
