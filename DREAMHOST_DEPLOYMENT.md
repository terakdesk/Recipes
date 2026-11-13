# DreamHost Deployment Guide for www.42wide.com/food55

**Server:** pdx1-shared-a3-07.dreamhost.com  
**User:** f42widec (no sudo access)  
**App Port:** 8055 (localhost only)

---

## Overview

Since you don't have sudo access, the deployment strategy is:
1. ✅ Deploy Flask app in your home directory as a regular user
2. ✅ Run Gunicorn on unprivileged port 8055
3. ⚠️ **Admin must configure nginx** to proxy `/food55` → `127.0.0.1:8055`
4. ✅ Set up persistent background process

---

## Step 1: Copy Files to DreamHost

From your Windows machine (PowerShell), copy all app files:

```powershell
$user = "f42widec"
$host = "pdx1-shared-a3-07.dreamhost.com"

# Copy individual files
scp c:\Users\miket\Recipes_remote\app.py $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\recipes.db $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\requirements.txt $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\filtered_tags.py $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\dreamhost_deploy.sh $user@$host:~/recipes_remote/

# Copy directories
scp -r c:\Users\miket\Recipes_remote\templates $user@$host:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\static $user@$host:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\saved_recipes_json $user@$host:~/recipes_remote/
```

When prompted, enter your SSH password.

---

## Step 2: SSH Into DreamHost and Run Setup

```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
# Enter your SSH password when prompted

cd ~/recipes_remote
bash dreamhost_deploy.sh
```

The script will:
- ✓ Create Python virtual environment
- ✓ Install Flask and Gunicorn
- ✓ Verify all required files
- ✓ Create startup script
- ✓ Test Flask installation
- ✓ Display Flask secret key (save this!)

Expected output:
```
==========================================
✅ DEPLOYMENT COMPLETE!
==========================================

Next steps:
1. Copy this startup script...
2. Start the app in the background...
3. Verify it's running...
...
```

---

## Step 3: Start the Flask App

On the DreamHost server, in the SSH session:

```bash
cd ~/recipes_remote

# Start in background and capture output
nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid

# Verify it's running (wait a few seconds)
sleep 3
ps -p $(cat gunicorn.pid)
```

You should see output like:
```
f42widec 12345 0.0 0.5 123456 78901 ? S 13:45:00 /home/f42widec/recipes_remote/.venv/bin/python3
```

---

## Step 4: Verify Local Access

Still in SSH session:

```bash
# Test if Gunicorn is listening on port 8055
netstat -tuln | grep 8055
# OR
ss -tuln | grep 8055

# Test direct connection
curl http://127.0.0.1:8055/

# You should get HTML output from the search page
```

If it works, you'll see the recipes search page HTML.

**If it fails:**

Check the error log:
```bash
tail -50 ~/recipes_remote/error.log
```

Common issues:
- Missing dependencies: `pip install beautifulsoup4 requests`
- Database not found: `ls -la ~/recipes_remote/recipes.db`
- Port conflicts: `lsof -i :8055` to see what's using it

---

## Step 5: Contact DreamHost Admin for nginx Configuration

Send this to the DreamHost admin (or add via control panel if available):

```
Hello,

I'm running a Flask app as user f42widec on localhost port 8055.
I need nginx configured to proxy www.42wide.com/food55 to this app.

Please add this location block to the nginx config for www.42wide.com:

---BEGIN---
location /food55/ {
    rewrite ^/food55/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:8055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /food55/static/ {
    alias /home/f42widec/recipes_remote/static/;
    expires 30d;
}
---END---

After adding these, please run:
  nginx -t
  systemctl reload nginx

Then let me know when it's live.
Thanks!
```

---

## Step 6: Test the Deployment

Once admin confirms nginx is configured:

### From Windows machine:

```powershell
# Test basic page
curl http://www.42wide.com/food55/

# Test search functionality
curl "http://www.42wide.com/food55/?q=beef"

# Test a recipe detail page (once you know a recipe ID)
curl "http://www.42wide.com/food55/recipe/123"
```

Or visit in browser: **http://www.42wide.com/food55/**

### From DreamHost server (still in SSH):

```bash
# Check nginx logs for errors
tail -20 /var/log/nginx/error.log  # might not have permission
# OR ask admin to check

# Check gunicorn logs
tail -20 ~/recipes_remote/error.log
tail -20 ~/recipes_remote/access.log
```

---

## Step 7: Persistent Background Running

Your app is now running with `nohup`. To ensure it survives server restart:

### Option A: Add to crontab (Recommended)

```bash
crontab -e
```

Add this line:

```
@reboot cd $HOME/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &
```

Save and exit. App will restart automatically after server reboot.

### Option B: Create a monitoring script

If the app crashes, this will restart it automatically.

Create `~/recipes_remote/monitor.sh`:

```bash
#!/bin/bash

PIDFILE="$HOME/recipes_remote/gunicorn.pid"
START_SCRIPT="$HOME/recipes_remote/start.sh"
LOG_FILE="$HOME/recipes_remote/monitor.log"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_and_restart() {
    if [ ! -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        log_msg "Gunicorn not running, starting..."
        cd "$HOME/recipes_remote"
        nohup $START_SCRIPT >> gunicorn.log 2>&1 &
        echo $! > $PIDFILE
        log_msg "Started with PID $(cat $PIDFILE)"
    fi
}

log_msg "Monitor started"

while true; do
    check_and_restart
    sleep 300  # Check every 5 minutes
done
```

Make it executable and run:

```bash
chmod +x ~/recipes_remote/monitor.sh
nohup ~/recipes_remote/monitor.sh > /dev/null 2>&1 &
echo $! > ~/recipes_remote/monitor.pid
```

---

## Stopping/Managing the App

```bash
# Stop Gunicorn
kill $(cat ~/recipes_remote/gunicorn.pid)
rm ~/recipes_remote/gunicorn.pid

# View logs
tail -f ~/recipes_remote/error.log
tail -f ~/recipes_remote/access.log

# Check if running
ps -p $(cat ~/recipes_remote/gunicorn.pid) && echo "Running" || echo "Not running"

# Restart
kill $(cat ~/recipes_remote/gunicorn.pid) 2>/dev/null
sleep 2
cd ~/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
```

---

## Troubleshooting

### Port 8055 already in use

```bash
# Find what's using it
lsof -i :8055
# Kill it
kill -9 <PID>
```

### Database permission error

```bash
ls -la ~/recipes_remote/recipes.db
chmod 644 ~/recipes_remote/recipes.db
```

### App crashes or slow to start

```bash
# Check gunicorn error log
tail -100 ~/recipes_remote/error.log

# Test Flask directly
cd ~/recipes_remote
source .venv/bin/activate
python3 -c "from app import app; print('Flask OK')"

# Start Flask dev server to debug
python3 app.py
```

### Missing dependencies

```bash
cd ~/recipes_remote
source .venv/bin/activate
pip list | grep -i flask
pip install beautifulsoup4 requests
```

### Can't connect from Windows

```bash
# On DreamHost, verify port is listening
netstat -tuln | grep 8055

# On Windows, check if site is reachable
nslookup www.42wide.com
curl -v http://www.42wide.com/food55/
```

---

## File Structure

After deployment, your DreamHost home should look like:

```
~/recipes_remote/
├── app.py                    # Main Flask app
├── recipes.db               # SQLite database
├── requirements.txt         # Python dependencies list
├── filtered_tags.py         # HTML parser utility
├── dreamhost_deploy.sh      # This deployment script
├── start.sh                 # Startup script (created by deploy)
├── gunicorn.pid             # PID file (created when running)
├── gunicorn.log             # Gunicorn output log
├── access.log               # HTTP access log
├── error.log                # Error log
├── .venv/                   # Python virtual environment
├── templates/               # Jinja HTML templates
│   ├── index.html
│   ├── recipe.html
│   ├── edit.html
│   └── import.html
├── static/                  # CSS, JS, images
│   ├── style.css
│   └── ...
└── saved_recipes_json/      # Recipe JSON files (809 files)
    ├── recipe1.json
    ├── recipe2.json
    └── ...
```

---

## Quick Reference: Commands You'll Need

```bash
# SSH in
ssh f42widec@pdx1-shared-a3-07.dreamhost.com

# Copy files (from Windows)
scp c:\Users\miket\Recipes_remote\* f42widec@pdx1-shared-a3-07.dreamhost.com:~/recipes_remote/

# Run deployment
cd ~/recipes_remote && bash dreamhost_deploy.sh

# Start app
cd ~/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 & echo $! > gunicorn.pid

# Check if running
ps -p $(cat ~/recipes_remote/gunicorn.pid)

# View logs
tail -f ~/recipes_remote/error.log

# Stop app
kill $(cat ~/recipes_remote/gunicorn.pid)

# Test locally
curl http://127.0.0.1:8055/

# Test from Windows (after nginx configured)
curl http://www.42wide.com/food55/
```

---

## Summary

1. **Copy files** to DreamHost via scp
2. **Run deployment script** (`dreamhost_deploy.sh`)
3. **Start app** with `nohup ./start.sh`
4. **Contact admin** to add nginx config
5. **Test at** www.42wide.com/food55
6. **Set up monitoring** with crontab or monitor.sh

**Expected timeline:** 15-30 minutes (mostly waiting for admin to configure nginx)

Good luck! Let me know if you hit any issues.
