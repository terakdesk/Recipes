# Deployment Guide for www.42wide.com/food55 (No Sudo Access)

## Constraints & Solution

Since you have SSH access as `f42widec@42wide.com` but **no sudo**, we need a user-level deployment strategy:

✅ **What you CAN do:**
- Create directories in your home (~)
- Run Python apps and services in your user context
- Create a Python venv in your home
- Run Flask/Gunicorn as your user

❌ **What you CAN'T do:**
- Modify /etc/systemd/system (systemd services)
- Modify /etc/nginx/sites-available (nginx config)
- Listen on privileged ports (<1024)
- Install system packages

---

## Deployment Strategy

Since nginx is already running and www.42wide.com/food3 works, the **admin must have configured nginx**. 

**You need to:**
1. **Contact the www.42wide.com admin** to add the /food55 location block to nginx
2. **Deploy your Flask app** in your home directory
3. **Run Gunicorn** on an unprivileged port (e.g., 8055)
4. **Provide admin with the port number** they need to proxy to

---

## Part 1: Request Admin to Add nginx Configuration

Send this to the www.42wide.com administrator:

```
Please add this location block to the www.42wide.com nginx config
(in whichever site config handles /food3):

---
location /food55/ {
    # Remove /food55 prefix before passing to Flask app
    rewrite ^/food55/(.*)$ /$1 break;
    
    proxy_pass http://localhost:8055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /food55;
}

location /food55/static/ {
    alias /home/f42widec/recipes_remote/static/;
    expires 30d;
}
---

After adding this, please test with:
  sudo nginx -t
  sudo systemctl reload nginx
```

**Once they confirm it's done**, proceed to Part 2.

---

## Part 2: Deploy Flask App (No Sudo)

### Step 1: SSH into the server

```bash
ssh f42widec@42wide.com
```

### Step 2: Create app directory

```bash
cd ~
mkdir -p recipes_remote
cd recipes_remote
```

### Step 3: Copy files from your local machine

From your Windows machine (PowerShell):

```powershell
# Copy all necessary files
scp c:\Users\miket\Recipes_remote\app.py f42widec@42wide.com:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\recipes.db f42widec@42wide.com:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\requirements.txt f42widec@42wide.com:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\filtered_tags.py f42widec@42wide.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\templates f42widec@42wide.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\static f42widec@42wide.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\saved_recipes_json f42widec@42wide.com:~/recipes_remote/
```

### Step 4: Set up Python environment (on the server)

```bash
cd ~/recipes_remote

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Verify installation
python3 -c "import flask; import gunicorn; print('✓ All dependencies installed')"
```

### Step 5: Create startup script

Create `~/recipes_remote/start.sh`:

```bash
#!/bin/bash
cd ~/recipes_remote
source .venv/bin/activate
export FLASK_SECRET_KEY="your-secure-random-key-change-me"
export RECIPES_SESSION_TIMEOUT_MINUTES="60"
export APPLICATION_ROOT="/food55"

# Run on port 8055 (unprivileged)
exec gunicorn \
  --workers 3 \
  --worker-class sync \
  --bind 127.0.0.1:8055 \
  --access-logfile ~/recipes_remote/access.log \
  --error-logfile ~/recipes_remote/error.log \
  --log-level info \
  app:app
```

Make it executable:

```bash
chmod +x ~/recipes_remote/start.sh
```

### Step 6: Run the app

**Option A: Direct run (for testing)**

```bash
cd ~/recipes_remote
./start.sh
```

You should see:
```
[2026-11-11 13:30:00] [INFO] Starting gunicorn 21.0.0
[2026-11-11 13:30:00] [INFO] Listening at: http://127.0.0.1:8055
[2026-11-11 13:30:00] [INFO] Worker process spawned
```

**Option B: Background run (persistent)**

Use `nohup` to keep it running after SSH logout:

```bash
nohup ~/recipes_remote/start.sh > ~/recipes_remote/gunicorn.log 2>&1 &
echo $! > ~/recipes_remote/gunicorn.pid
```

Check it's running:

```bash
cat ~/recipes_remote/gunicorn.pid
ps -p $(cat ~/recipes_remote/gunicorn.pid)
```

**Option C: Long-running terminal multiplexer (tmux/screen)**

```bash
# Using tmux (if available)
tmux new-session -d -s recipes -c ~/recipes_remote "./start.sh"
tmux list-sessions
tmux attach-session -t recipes  # to view output
```

---

## Part 3: Modify Flask App for Subpath

Since the app runs at `/food55/`, Flask needs to know its base path.

Edit `app.py` and add this after the Flask imports (around line 15):

```python
from werkzeug.middleware.proxy_fix import ProxyFix

# After: app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Add configuration for subpath
SCRIPT_NAME = os.environ.get('X_SCRIPT_NAME', '/food55')
```

Then ensure all templates use `url_for()` for links (they should already).

Update `start.sh` to include:

```bash
export X_SCRIPT_NAME="/food55"
```

---

## Part 4: Verify Deployment

Once nginx is configured by the admin, test:

```bash
# From your Windows machine
curl http://www.42wide.com/food55/
```

Or visit in browser: `http://www.42wide.com/food55/`

Check logs on the server:

```bash
# View gunicorn logs
tail -f ~/recipes_remote/gunicorn.log

# View access logs
tail -f ~/recipes_remote/access.log

# View error logs
tail -f ~/recipes_remote/error.log
```

---

## Part 5: Keep App Running (No Systemd)

Since you can't use systemd, here are alternatives:

### Option 1: crontab (Restart on reboot)

Edit crontab:

```bash
crontab -e
```

Add this line:

```
@reboot /home/f42widec/recipes_remote/start.sh >> /home/f42widec/recipes_remote/cron.log 2>&1 &
```

### Option 2: Simple monitoring script

Create `~/recipes_remote/monitor.sh`:

```bash
#!/bin/bash

PIDFILE=~/recipes_remote/gunicorn.pid
START_SCRIPT=~/recipes_remote/start.sh

check_and_restart() {
    if [ ! -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "[$(date)] Gunicorn not running, starting..."
        nohup $START_SCRIPT >> ~/recipes_remote/gunicorn.log 2>&1 &
        echo $! > $PIDFILE
    fi
}

# Run every 5 minutes
while true; do
    check_and_restart
    sleep 300
done
```

Run in background:

```bash
nohup ~/recipes_remote/monitor.sh > ~/recipes_remote/monitor.log 2>&1 &
```

### Option 3: Request admin to use supervisor

If the server has `supervisor` installed (user-installable), it can manage your app:

```bash
pip install --user supervisor
```

---

## Stopping the App

If running with nohup:

```bash
# Stop the running process
kill $(cat ~/recipes_remote/gunicorn.pid)
rm ~/recipes_remote/gunicorn.pid
```

If using tmux:

```bash
tmux kill-session -t recipes
```

---

## Troubleshooting

### App won't start
```bash
# Test Flask directly
cd ~/recipes_remote
source .venv/bin/activate
python3 app.py
```

### Port already in use
```bash
# Find process using port 8055
lsof -i :8055
# Kill it
kill -9 <PID>
```

### nginx can't reach the app
```bash
# Verify app is listening
netstat -tuln | grep 8055
# Or:
ss -tuln | grep 8055
```

### Database permission errors
```bash
# Ensure database is readable by your user
ls -la ~/recipes_remote/recipes.db
# Should be: -rw-r--r-- (or similar)
```

### Missing dependencies
```bash
cd ~/recipes_remote
source .venv/bin/activate
pip install beautifulsoup4 requests
```

---

## Deployment Checklist

- [ ] Contact admin to add nginx location blocks for /food55
- [ ] Admin confirms nginx config is added and reloaded
- [ ] SSH into f42widec@42wide.com
- [ ] Create ~/recipes_remote directory
- [ ] Copy all app files via scp
- [ ] Create Python venv and install dependencies
- [ ] Create start.sh script
- [ ] Test app with `./start.sh` (direct run)
- [ ] Verify nginx can reach app at localhost:8055
- [ ] Test www.42wide.com/food55/ in browser
- [ ] Set up persistent running (nohup or crontab)
- [ ] Verify logs for any errors
- [ ] Test recipe search, detail pages, static files

---

## Admin Request Template

Copy/paste this to send to the www.42wide.com administrator:

```
Hi,

I'd like to deploy a Flask-based recipe web app at www.42wide.com/food55 
(alongside the existing www.42wide.com/food3).

I've prepared the app to run as user f42widec on port 8055 (localhost only).

Could you please add this nginx location block to the www.42wide.com config:

---BEGIN---
location /food55/ {
    rewrite ^/food55/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:8055;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /food55;
}

location /food55/static/ {
    alias /home/f42widec/recipes_remote/static/;
    expires 30d;
}
---END---

After adding these lines, please run:
  sudo nginx -t
  sudo systemctl reload nginx

Then let me know when it's live. Thank you!
```

---

## Questions?

If you run into issues:
1. Check logs: `tail -f ~/recipes_remote/error.log`
2. Test Flask directly: `python3 app.py`
3. Verify network: `curl http://127.0.0.1:8055/`
4. Check database: `ls -la ~/recipes_remote/recipes.db`

Let me know the results!
