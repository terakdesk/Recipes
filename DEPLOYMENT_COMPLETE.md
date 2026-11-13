# DreamHost Recipes Deployment - Complete Setup Guide

## Deployment Summary
- **URL**: http://www.42wide.com/food55/
- **Host**: pdx1-shared-a3-07.dreamhost.com
- **User**: f42widec
- **Flask App**: Running on 127.0.0.1:8055 with 3 gunicorn workers
- **Database**: SQLite (recipes.db) with 809 recipes
- **Proxy**: PHP wrapper + Apache mod_rewrite

---

## Architecture

```
Browser (www.42wide.com/food55/)
    ↓
Apache Web Server (port 80/443)
    ↓
.htaccess rewrite (mod_rewrite)
    ↓
PHP Wrapper (index.php)
    - Strips /food55 prefix from URL
    - Adds X-Script-Name header
    - Proxies to Flask
    - Rewrites response paths to add /food55
    ↓
Flask App (127.0.0.1:8055)
    - Custom ScriptNameMiddleware reads X-Script-Name
    - Generates correct URLs with /food55 prefix
    - Serves recipes from SQLite database
```

---

## Directory Structure

```
/home/f42widec/recipes_remote/          # Flask app directory
├── app.py                              # Main Flask application
├── recipes.db                          # SQLite database (809 recipes)
├── requirements.txt                    # Python dependencies
├── filtered_tags.py                    # Tag filtering utility
├── logo_header_chez_michel.png          # Logo image
├── .venv/                              # Python virtual environment
├── templates/                          # Flask HTML templates
├── static/                             # Static assets (CSS, images)
├── saved_recipes_json/                 # Recipe backup in JSON format
├── start.sh                            # Startup script for Flask
├── check_and_restart_flask.sh           # Auto-restart health check
├── backup_recipes.sh                   # Database backup script
├── gunicorn.pid                        # Process ID (auto-managed)
├── access.log                          # Access log
├── error.log                           # Error log
└── restart.log                         # Auto-restart log

/home/f42widec/42wide.com/food55/       # Web-accessible proxy directory
├── index.php                           # PHP proxy wrapper
├── .htaccess                           # Apache rewrite rules
└── logo_header_chez_michel.png         # Logo (served directly)
```

---

## Configuration Files

### 1. app.py - Flask Application
**Location**: `/home/f42widec/recipes_remote/app.py`

Key features:
- Custom `ScriptNameMiddleware` class handles X-Script-Name header
- Sets SCRIPT_NAME from X-Script-Name header (sent by PHP proxy)
- url_for() and redirect() automatically generate URLs with /food55 prefix
- SQLite database access with 809 recipes
- User authentication (login system)
- Recipe import/export functionality

### 2. index.php - PHP Proxy Wrapper
**Location**: `/home/f42widec/42wide.com/food55/index.php`

Responsibilities:
- Receives all requests to /food55/*
- Strips /food55 prefix from REQUEST_URI
- Adds X-Script-Name: /food55 header
- cURL requests to Flask on 127.0.0.1:8055
- Receives Flask response
- Rewrites HTML paths to add /food55 prefix
  - href="/" → href="/food55/"
  - src="/" → src="/food55/"
  - action="/" → action="/food55/"
- Forwards response headers and body to browser

### 3. .htaccess - Apache Rewrite Rules
**Location**: `/home/f42widec/42wide.com/food55/.htaccess`

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /food55/
    
    # Don't rewrite real files or directories
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    
    # Rewrite all requests to index.php
    RewriteRule ^(.*)$ index.php [L]
</IfModule>
```

This ensures all requests go through the PHP proxy.

### 4. start.sh - Flask Startup Script
**Location**: `/home/f42widec/recipes_remote/start.sh`

Starts gunicorn with:
- 3 worker processes
- Sync worker class
- Binding to 127.0.0.1:8055
- Access and error logging
- Flask secret key from environment

---

## Running the Application

### Manual Start
```bash
cd /home/f42widec/recipes_remote
./start.sh &
```

### Manual Stop
```bash
pkill -f "gunicorn.*app:app"
```

### Check Status
```bash
ps aux | grep gunicorn | grep -v grep
curl http://127.0.0.1:8055/
curl http://www.42wide.com/food55/
```

---

## Auto-Restart Setup

### Purpose
Automatically restart Flask if the process crashes or stops running.

### Installation
```bash
# 1. Copy the check script to DreamHost
scp /local/path/check_and_restart_flask.sh f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/

# 2. Make it executable
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "chmod +x /home/f42widec/recipes_remote/check_and_restart_flask.sh"

# 3. Add to crontab (runs every 5 minutes)
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "crontab -e"
```

### Crontab Entry
Add this line to your crontab:
```
*/5 * * * * /home/f42widec/recipes_remote/check_and_restart_flask.sh
```

This runs the health check every 5 minutes and restarts Flask if needed.

### Monitor Restarts
```bash
# View restart log
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -20 /home/f42widec/recipes_remote/restart.log"

# Follow restart log in real-time
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -f /home/f42widec/recipes_remote/restart.log"
```

---

## Backup Strategy

### Purpose
Regular automated backups of the recipes database to prevent data loss.

### Installation
```bash
# 1. Copy the backup script to DreamHost
scp /local/path/backup_recipes.sh f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/

# 2. Make it executable
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "chmod +x /home/f42widec/recipes_remote/backup_recipes.sh"

# 3. Add to crontab (runs daily at 2 AM)
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "crontab -e"
```

### Crontab Entry
Add this line to your crontab:
```
0 2 * * * /home/f42widec/recipes_remote/backup_recipes.sh
```

This backs up the database every day at 2 AM.

### Manual Backup
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "/home/f42widec/recipes_remote/backup_recipes.sh"
```

### Viewing Backups
```bash
# List all backups
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "ls -lh /home/f42widec/recipes_remote/backups/"

# Get latest backup
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cat /home/f42widec/recipes_remote/backups/recipes.db.latest"

# Download backup to local machine
scp f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/backups/recipes.db.latest ./recipes_backup.db
```

### Restore from Backup
```bash
# Copy backup to DreamHost recipes_remote directory
scp ./recipes_backup.db f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/recipes.db

# Restart Flask to use new database
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "pkill -f gunicorn; sleep 2; cd /home/f42widec/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &"
```

---

## Database

### Location
`/home/f42widec/recipes_remote/recipes.db`

### Size
~4 MB SQLite database

### Contents
- 809 recipes with:
  - Title
  - Ingredients
  - Instructions
  - Preamble/notes
  - Created/modified dates
  - Tags and categories

### Backup Location
`/home/f42widec/recipes_remote/backups/recipes.db.backup_YYYYMMDD_HHMMSS`

---

## Troubleshooting

### Flask Not Running
```bash
# Check if process exists
ps aux | grep gunicorn | grep -v grep

# Check Flask logs
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -50 /home/f42widec/recipes_remote/error.log"

# Test Flask directly
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "curl -s http://127.0.0.1:8055/"

# Manually restart
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cd /home/f42widec/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &"
```

### URLs Not Working
Check that .htaccess is correct:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cat /home/f42widec/42wide.com/food55/.htaccess"
```

Verify PHP proxy is working:
```bash
curl http://www.42wide.com/food55/ | head -20
```

### 404 Errors
- Ensure .htaccess is in place and readable
- Check that index.php exists in /home/f42widec/42wide.com/food55/
- Verify Flask is responding: `curl http://127.0.0.1:8055/`

### Logo Not Showing
Logo file should be at:
- `/home/f42widec/recipes_remote/logo_header_chez_michel.png` (for Flask)
- `/home/f42widec/42wide.com/food55/logo_header_chez_michel.png` (for direct web access)

Test logo:
```bash
curl -I http://www.42wide.com/food55/logo_header_chez_michel.png
```

### Login Issues
Check that X-Script-Name header is being sent by PHP wrapper.

Test with header:
```bash
curl -H "X-Script-Name: /food55" http://127.0.0.1:8055/import
```

---

## Maintenance Tasks

### Daily
- Monitor restart.log for unexpected restarts
- Check backup.log for successful backups

### Weekly
- Verify database integrity: `ssh f42widec@... "sqlite3 /home/f42widec/recipes_remote/recipes.db 'PRAGMA integrity_check;'"`
- Check for Flask errors in error.log
- Test main functionality: http://www.42wide.com/food55/

### Monthly
- Download and store backup locally
- Review logs for patterns or issues
- Check disk space: `ssh f42widec@... "df -h /home/f42widec"`

---

## SSH Access

### Connection Info
```
Host: pdx1-shared-a3-07.dreamhost.com
User: f42widec
Auth: Password (can set up SSH keys for passwordless access)
```

### Connect
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
```

### Set Up SSH Key (Optional - for passwordless access)
```bash
# Generate key locally (if not already done)
ssh-keygen -t ed25519 -f ~/.ssh/dreamhost_recipes

# Copy to DreamHost
ssh-copy-id -i ~/.ssh/dreamhost_recipes.pub f42widec@pdx1-shared-a3-07.dreamhost.com

# Update SSH config (~/.ssh/config)
Host dreamhost-recipes
    HostName pdx1-shared-a3-07.dreamhost.com
    User f42widec
    IdentityFile ~/.ssh/dreamhost_recipes

# Now connect with: ssh dreamhost-recipes
```

---

## Environment Variables

### Flask Configuration
Set in `start.sh`:
- `FLASK_SECRET_KEY`: Encryption key for sessions (auto-generated during deployment)
- `RECIPES_SESSION_TIMEOUT_MINUTES`: Session timeout in minutes (default: 30)
- `X_SCRIPT_NAME`: Set by PHP proxy (added as header, not env var)

---

## Performance Notes

### Resource Usage
- Flask: ~27MB RAM (main process)
- Workers: ~32MB RAM each (3 workers)
- Total: ~120MB for Flask + gunicorn

### Scaling
If performance degrades:
1. Increase worker count in start.sh: `--workers 5`
2. Monitor access.log for slow requests
3. Check database for missing indexes

### Caching
- Apache caches static content via Cache-Control headers
- Set browser cache: checked (modern browsers)
- Database queries are not cached (reads fresh data each time)

---

## Disaster Recovery

### Complete Restore Procedure

If the entire deployment needs to be recreated:

1. **Copy files from backup**
   ```bash
   scp recipes_backup.db f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/recipes.db
   ```

2. **Redeploy app files** (same as initial deployment)
   ```bash
   scp app.py start.sh requirements.txt ... f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/
   ```

3. **Reinstall dependencies**
   ```bash
   ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cd /home/f42widec/recipes_remote && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
   ```

4. **Start Flask**
   ```bash
   ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cd /home/f42widec/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &"
   ```

5. **Verify**
   ```bash
   curl http://www.42wide.com/food55/
   ```

---

## Change Log

### Version 1.0 - November 11, 2026
- Initial deployment to DreamHost
- 809 recipes synced from home server (192.168.2.10)
- PHP proxy wrapper with Apache rewrite
- Flask with custom ScriptNameMiddleware
- Auto-restart health check
- Automated backup script
- Complete documentation

---

## Support & Next Steps

### Common Tasks

**Add a new recipe**
- Login: http://www.42wide.com/food55/login
- Import: http://www.42wide.com/food55/import

**Search recipes**
- Main page: http://www.42wide.com/food55/
- Search by keyword: http://www.42wide.com/food55/?q=curry

**View recipe**
- Click any recipe from search results
- Edit if logged in: http://www.42wide.com/food55/recipe/[ID]/edit

**Backup database**
- Automatic: Daily at 2 AM
- Manual: `/home/f42widec/recipes_remote/backup_recipes.sh`

**Monitor application**
- Status: `ps aux | grep gunicorn`
- Logs: `tail /home/f42widec/recipes_remote/error.log`
- Restarts: `tail /home/f42widec/recipes_remote/restart.log`

---

## Contact & Updates

For questions or issues with the deployment, refer to:
1. This guide for common troubleshooting
2. Application logs in /home/f42widec/recipes_remote/
3. DreamHost support for server-level issues

Last updated: November 11, 2026
