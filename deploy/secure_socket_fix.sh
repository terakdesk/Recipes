#!/bin/sh
# Deploy script to apply secure runtime-socket fix on the server.
# Run this on the server from your home folder (~/recipes_remote).

set -euo pipefail

# Install systemd unit from repo
sudo cp ~/recipes_remote/deploy/recipes.service /etc/systemd/system/recipes.service
sudo systemctl daemon-reload
sudo systemctl restart recipes.service

# Verify runtime dir and socket
echo "Runtime dir and socket (should exist after service start):"
ls -ld /run/recipes || true
ls -l /run/recipes/recipes.sock || true

# Install nginx site
sudo cp ~/recipes_remote/deploy/recipes_nginx /etc/nginx/sites-available/recipes
sudo ln -sf /etc/nginx/sites-available/recipes /etc/nginx/sites-enabled/recipes
sudo nginx -t
sudo systemctl reload nginx

# Quick checks
echo "HTTP test (from server):"
curl -I --unix-socket /run/recipes/recipes.sock http://localhost/ || true
curl -I http://127.0.0.1/ || true

# Tail logs for quick troubleshooting
sudo journalctl -u recipes.service -n 200 --no-pager || true
sudo tail -n 200 /var/log/nginx/error.log || true
