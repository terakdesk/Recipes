#!/bin/bash
# DreamHost Deployment Script for Recipes App at www.42wide.com/food55
# Run this on the DreamHost server as user f42widec
# Usage: bash dreamhost_deploy.sh

set -e  # Exit on any error

echo "=========================================="
echo "DreamHost Recipes App Deployment"
echo "=========================================="

# Configuration
APP_DIR="$HOME/recipes_remote"
VENV_DIR="$APP_DIR/.venv"
PORT="8055"
FLASK_SECRET_KEY="$(openssl rand -base64 32)"

echo ""
echo "[1/7] Creating app directory..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "[2/7] Checking Python availability..."
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: python3 not found. Check with admin."
    exit 1
fi
python3 --version

echo "[3/7] Creating Python virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "  Virtual environment already exists, skipping..."
else
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
fi

echo "[4/7] Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install Flask>=2.0 gunicorn > /dev/null 2>&1
echo "✓ Dependencies installed"

echo "[5/7] Verifying required files exist..."
for file in app.py recipes.db requirements.txt filtered_tags.py; do
    if [ ! -f "$file" ]; then
        echo "❌ ERROR: Missing $file"
        echo "  Please copy all files to $APP_DIR before running this script"
        exit 1
    fi
done
ls -1 templates/ > /dev/null 2>&1 || { echo "❌ Missing templates/ directory"; exit 1; }
ls -1 static/ > /dev/null 2>&1 || { echo "❌ Missing static/ directory"; exit 1; }
echo "✓ All required files present"

echo "[6/7] Creating startup script..."
cat > "$APP_DIR/start.sh" << 'STARTSCRIPT'
#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate
export FLASK_SECRET_KEY="${FLASK_SECRET_KEY:-your-secret-key}"
export RECIPES_SESSION_TIMEOUT_MINUTES="60"
export X_SCRIPT_NAME="/food55"

exec gunicorn \
  --workers 3 \
  --worker-class sync \
  --bind 127.0.0.1:8055 \
  --access-logfile access.log \
  --error-logfile error.log \
  --log-level info \
  app:app
STARTSCRIPT

chmod +x "$APP_DIR/start.sh"
echo "✓ Startup script created"

echo "[7/7] Testing Flask app..."
source "$VENV_DIR/bin/activate"
python3 -c "import flask, gunicorn; print('✓ Flask and Gunicorn verified')" || exit 1

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Copy this startup script to a persistent location:"
echo "   cat $APP_DIR/start.sh"
echo ""
echo "2. Start the app in the background:"
echo "   cd $APP_DIR"
echo "   nohup ./start.sh > gunicorn.log 2>&1 &"
echo "   echo \$! > gunicorn.pid"
echo ""
echo "3. Verify it's running:"
echo "   sleep 3"
echo "   curl http://127.0.0.1:8055/"
echo ""
echo "4. Contact admin to add this nginx config:"
echo "   location /food55/ {"
echo "       rewrite ^/food55/(.*)$ /\$1 break;"
echo "       proxy_pass http://127.0.0.1:8055;"
echo "       proxy_set_header Host \$host;"
echo "       proxy_set_header X-Real-IP \$remote_addr;"
echo "       proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
echo "       proxy_set_header X-Forwarded-Proto \$scheme;"
echo "   }"
echo ""
echo "5. Test at: http://www.42wide.com/food55/"
echo ""
echo "=========================================="
echo "Flask Secret Key (save this):"
echo "$FLASK_SECRET_KEY"
echo "=========================================="
