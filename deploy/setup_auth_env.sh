#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/home/me/recipes_remote/.venv/bin/python"
SERVICE_FILE="/etc/systemd/system/recipes.service"
ENV_FILE="/etc/recipes.env"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing Python interpreter at $PYTHON_BIN" >&2
  exit 1
fi

read -r -p "Enter auth username [admin]: " APP_USER
APP_USER=${APP_USER:-admin}

read -r -s -p "Enter NEW app password: " APP_PASS
echo
read -r -s -p "Confirm NEW app password: " APP_PASS2
echo

if [ "$APP_PASS" != "$APP_PASS2" ]; then
  echo "Passwords do not match. Aborting." >&2
  exit 1
fi

if [ ${#APP_PASS} -lt 8 ]; then
  echo "Password must be at least 8 characters. Aborting." >&2
  exit 1
fi

APP_HASH=$(APP_PASS="$APP_PASS" "$PYTHON_BIN" -c "from werkzeug.security import generate_password_hash; import os; print(generate_password_hash(os.environ['APP_PASS']))")
SECRET_KEY=$($PYTHON_BIN -c "import secrets; print(secrets.token_urlsafe(48))")

printf "FLASK_SECRET_KEY=%s\nRECIPES_AUTH_USER=%s\nRECIPES_AUTH_PASSWORD_HASH=%s\n" "$SECRET_KEY" "$APP_USER" "$APP_HASH" | sudo tee "$ENV_FILE" >/dev/null
sudo chmod 600 "$ENV_FILE"

if ! sudo grep -q '^EnvironmentFile=/etc/recipes.env$' "$SERVICE_FILE"; then
  sudo sed -i '/^Environment=PATH=.*/a EnvironmentFile=/etc/recipes.env' "$SERVICE_FILE"
fi

sudo systemctl daemon-reload
sudo systemctl restart recipes.service
sudo systemctl status recipes.service --no-pager -n 12

echo
echo "Auth env configured successfully."
