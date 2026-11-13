# Recipes

A personal cookbook: store recipes locally, search them, and add or edit them in the browser.

Recipes live as JSON on disk and in a SQLite database. A small Flask app is the UI. Many of the current recipes were scraped from [42wide.com/food3](https://www.42wide.com/food3/index.php) and parsed into structured files.

**🌐 Live at production:** http://www.42wide.com/food55/ (DreamHost Apache + PHP proxy)

## What you get

- Browse and search recipes by title or ingredients
- Open a recipe (ingredients, method, notes, details)
- Import by pasting text or HTML
- Edit an existing recipe (requires login)
- Auto-restart on failure
- Daily automated backups

## How the pieces connect

```
auto_scraper.py          →  saved_recipes/*.html
filtered_tags.py         →  saved_recipes_json/*.json
merge_json_to_sqlite.py  →  recipes.db
create_fts.py            →  recipes_fts (full-text search)
app.py + templates/      →  Local: http://127.0.0.1:5000
                         →  Production: http://www.42wide.com/food55/
deploy/                  →  systemd + nginx (local)
index.php + .htaccess    →  Apache + PHP proxy (DreamHost)
check_and_restart_flask.sh → Cron health-check (auto-restart)
backup_recipes.sh        →  Cron daily backup
```

| Path | Role |
|------|------|
| `app.py` | Flask routes, SQLite access, authentication. Includes `ScriptNameMiddleware` for reverse proxy support (reads X-Script-Name header for /food55 prefix) |
| `templates/` | Jinja pages (search, recipe, import, edit, login, user management) |
| `saved_recipes/` | Saved HTML source pages |
| `saved_recipes_json/` | Parsed recipes (`title`, `preamble`, `ingredients`, `method`, `notes`, `details`) |
| `recipes.db` | SQLite store used by the web app (built locally; not required in git) |
| `filtered_tags.py` | HTML → JSON parser (also used on import) |
| `merge_json_to_sqlite.py` | JSON files → `recipes` table |
| `create_fts.py` | Rebuilds `recipes_fts` for search |
| `auto_scraper.py` | Crawls the original site into `saved_recipes/` |
| `deploy/` | Gunicorn unix socket + nginx (local production) |
| `index.php` | PHP proxy wrapper for Apache (DreamHost production). Strips /food55 prefix, proxies to Flask, rewrites paths and Location headers |
| `.htaccess` | Apache mod_rewrite rules (DreamHost production) |
| `check_and_restart_flask.sh` | Cron job: health-check script that auto-restarts Flask every 5 minutes if crashed |
| `backup_recipes.sh` | Cron job: daily backup script at 2 AM, keeps 30 most recent backups |

## Run locally

Python 3 and a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` lists Flask. For HTML parsing and scraping, also install:

```bash
pip install beautifulsoup4 requests
```

Build the database from the JSON files, then start the app:

```bash
python merge_json_to_sqlite.py
python create_fts.py
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Rebuild `recipes.db` and the FTS index whenever you add or change JSON files on disk. Edits made in the web UI write to SQLite only.

### Useful routes

| URL | What it does |
|-----|----------------|
| `/` | Search and list |
| `/recipe/<id>` | View one recipe |
| `/recipe/<id>/edit` | Edit |
| `/import` | Paste text/HTML, preview, then save |

## Rebuild data from HTML

If you have HTML in `saved_recipes/` and want fresh JSON:

```bash
python filtered_tags.py --src saved_recipes --out saved_recipes_json
python merge_json_to_sqlite.py
python create_fts.py
```

Re-running the scraper (`python auto_scraper.py`) crawls `42wide.com` again. Use that only when you intend to fetch live pages.

## Production Deployment

### DreamHost (Apache + PHP Proxy)

The app is live in production at **http://www.42wide.com/food55/**

**Architecture:**
- **Web Server**: Apache (DreamHost shared hosting)
- **Flask Backend**: Gunicorn on 127.0.0.1:8055
- **Proxy Layer**: PHP wrapper (`index.php`) that:
  - Strips `/food55` prefix from request
  - Adds `X-Script-Name: /food55` header for Flask
  - Proxies request to gunicorn via cURL
  - Rewrites response HTML paths to include `/food55`
  - **Rewrites Location headers** for redirects (login fix)
- **Rewrite Rules**: Apache mod_rewrite (`.htaccess`) routes all requests to `index.php`

**Features:**
- ✅ User authentication (login required for import/edit)
- ✅ Recipe search and browsing (809 recipes)
- ✅ Recipe editing and creation
- ✅ Auto-restart on crash (every 5 minutes via cron)
- ✅ Daily automated backups at 2 AM UTC (kept for 30 days)

**Monitoring & Maintenance:**

Check Flask status:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "ps aux | grep gunicorn"
```

View logs:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -50 /home/f42widec/recipes_remote/error.log"
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -20 /home/f42widec/recipes_remote/restart.log"
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "tail -20 /home/f42widec/recipes_remote/backup.log"
```

Manual restart:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "pkill -f gunicorn; sleep 2; cd /home/f42widec/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &"
```

Manual backup:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "/home/f42widec/recipes_remote/backup_recipes.sh"
```

**Important Files:**
- [DEPLOYMENT_COMPLETE.md](DEPLOYMENT_COMPLETE.md) - Full deployment guide with troubleshooting
- [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md) - Quick reference and commands
- [FIX_LOGIN_REDIRECT.md](FIX_LOGIN_REDIRECT.md) - Login redirect fix (applied Nov 11, 2026)

### Local Development

For local development, use the deploy/ directory with systemd + nginx:
See [deploy/README.md](deploy/README.md)


## Where to start as a newcomer

1. `app.py` — the whole web surface is this file. Contains authentication, recipe routes, and ScriptNameMiddleware for reverse proxy support.
2. `templates/index.html` — search UI.
3. Any file in `saved_recipes_json/` — the recipe JSON shape.
4. `merge_json_to_sqlite.py` — table schema and import.

---

## Recent Changes (November 11, 2026)

### 🚀 Deployed to Production (www.42wide.com/food55)
- Migrated Flask app from local network (192.168.2.10) to DreamHost public hosting
- Implemented Apache + PHP reverse proxy for /food55 URL prefix handling
- 809 recipes synced and now live in production
- Created comprehensive deployment documentation

### ✨ Added Features
1. **User Authentication**: Login required for import, edit, and user management features
2. **Auto-Restart**: Health check script runs every 5 minutes via cron, automatically restarts Flask if it crashes
3. **Automated Backups**: Daily backup at 2 AM UTC, keeps last 30 backups with logging

### 🔧 Code Changes
1. **app.py**: Added `ScriptNameMiddleware` class to read X-Script-Name header from PHP proxy, enabling Flask to generate correct /food55-prefixed URLs
2. **index.php**: 
   - New PHP proxy wrapper that strips /food55 prefix, proxies to gunicorn, rewrites response paths
   - Updated to rewrite Location headers for redirects (fixes login redirect issue)
3. **templates/login.html**: Added login page template with user authentication form
4. **.htaccess**: Apache mod_rewrite configuration to route all /food55/* requests to index.php

### 📄 New Files
- `check_and_restart_flask.sh` - Auto-restart health check script
- `backup_recipes.sh` - Daily database backup script
- `index.php` - Apache/PHP reverse proxy wrapper
- `.htaccess` - Apache rewrite rules
- `DEPLOYMENT_COMPLETE.md` - Full 13KB deployment guide
- `DEPLOYMENT_SUMMARY.md` - Quick reference guide
- `FIX_LOGIN_REDIRECT.md` - Login redirect fix documentation

### 🐛 Bugs Fixed
- **Login redirect issue** (Nov 11): Fixed PHP proxy not rewriting Location headers, causing redirect to blank page
  - Solution: Added regex-based Location header rewriting to include /food55 prefix

### 📊 Current Status
- **Production URL**: http://www.42wide.com/food55/
- **Recipes**: 809 (synced from local server 192.168.2.10)
- **Database**: SQLite (4 MB recipes.db)
- **Uptime**: Auto-restart every 5 minutes + daily backups
- **All features tested and working**: ✅ Search, ✅ Recipe view, ✅ Login, ✅ Edit, ✅ Import
