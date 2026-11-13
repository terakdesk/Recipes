# Deployment Guide: www.42wide.com/food55

## Current Status

- **Domain:** 42wide.com (Cloudflare CDN)
- **Current Path:** www.42wide.com/food3 (working, serving static recipes)
- **New Path:** www.42wide.com/food55 (to be deployed)
- **Local App:** Flask + SQLite, running at http://192.168.2.10 (working)
- **Remote Server:** ethel@192.168.2.10 running Ubuntu

## Deployment Approach

There are **two main strategies** to deploy to www.42wide.com/food55:

### **Option A: Deploy to Your Own Public Server (Recommended for Full Control)**

If you have a public-facing server or VPS:

1. **Deploy the Flask app on your public server** with its own domain/IP
2. **Update nginx on www.42wide.com** to proxy www.42wide.com/food55 to your Flask app
3. **Set up Let's Encrypt SSL** for HTTPS on the /food55 path

### **Option B: Deploy Within Existing 42wide.com Server (Requires Server Access)**

If the 42wide.com server is yours and accessible:

1. **SSH into the 42wide.com server** (wherever food3 is currently hosted)
2. **Deploy the Flask + Gunicorn app** on that server
3. **Update the /food55 path** in nginx to proxy to Gunicorn socket

---

## Prerequisites Checklist

### For Option A or B:
- [ ] Public server with SSH access and SSH key
- [ ] Python 3.8+ installed on the server
- [ ] nginx installed and running
- [ ] sudo/root access to manage systemd and nginx
- [ ] SQLite3 on the server
- [ ] Domain/DNS pointing to the server

### Additional Requirements for Option A:
- [ ] Static public IP or dynamic DNS
- [ ] Firewall rules allowing HTTP/HTTPS (ports 80, 443)

---

## Option A: Deploy Flask App to Separate Server (via www.42wide.com/food55 proxy)

### Step 1: Prepare Your Public Server

```bash
# SSH into your public server
ssh user@your.server.com

# Create app directory
mkdir -p ~/recipes_remote
cd ~/recipes_remote

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install Flask>=2.0 gunicorn beautifulsoup4 requests
```

### Step 2: Copy App Files to Server

From your local machine:

```bash
# Copy the recipes app to your server
scp -r c:\Users\miket\Recipes_remote\app.py user@your.server.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\recipes.db user@your.server.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\templates user@your.server.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\static user@your.server.com:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\saved_recipes_json user@your.server.com:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\filtered_tags.py user@your.server.com:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\requirements.txt user@your.server.com:~/recipes_remote/
```

### Step 3: Configure Gunicorn & systemd

**On your server**, create `/etc/systemd/system/recipes.service`:

```ini
[Unit]
Description=Recipes Flask app (gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/user/recipes_remote
Environment=PATH=/home/user/recipes_remote/.venv/bin
Environment=FLASK_SECRET_KEY=your-secure-secret-key-here
RuntimeDirectory=recipes
RuntimeDirectoryMode=0750
ExecStart=/home/user/recipes_remote/.venv/bin/gunicorn --workers 3 --bind unix:/run/recipes/recipes.sock app:app
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable recipes.service
sudo systemctl start recipes.service
```

### Step 4: Configure nginx on Your Server

Create `/etc/nginx/sites-available/recipes`:

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name your.server.com;

    # SSL (optional but recommended - use certbot)
    # ssl_certificate /etc/letsencrypt/live/your.server.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your.server.com/privkey.pem;

    # Gunicorn socket proxy
    location / {
        proxy_pass http://unix:/run/recipes/recipes.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/user/recipes_remote/static/;
        expires 30d;
    }
}
```

Enable and test:

```bash
sudo ln -sf /etc/nginx/sites-available/recipes /etc/nginx/sites-enabled/recipes
sudo nginx -t
sudo systemctl reload nginx
```

### Step 5: Update nginx on www.42wide.com (Proxy to Your Server)

**On the www.42wide.com server**, modify nginx to proxy /food55 path:

```nginx
location /food55/ {
    proxy_pass http://your.server.com:80/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Reload nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Option B: Deploy on 42wide.com Server (Direct Deployment)

**Note:** Requires access to the existing www.42wide.com server.

### Step 1: SSH into 42wide.com Server

```bash
ssh user@42wide.com.server.ip
# or wherever food3 is hosted
```

### Step 2: Deploy App

```bash
cd /var/www  # or appropriate app directory
git clone <your-repo-url> recipes_remote
cd recipes_remote

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Set Up Gunicorn with systemd

Create `/etc/systemd/system/recipes-food55.service`:

```ini
[Unit]
Description=Recipes Flask app for /food55 (gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/recipes_remote
Environment=PATH=/var/www/recipes_remote/.venv/bin
RuntimeDirectory=recipes-food55
RuntimeDirectoryMode=0750
ExecStart=/var/www/recipes_remote/.venv/bin/gunicorn --workers 3 --bind unix:/run/recipes-food55/recipes.sock app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable recipes-food55.service
sudo systemctl start recipes-food55.service
```

### Step 4: Add nginx Location Block for /food55

Edit the main nginx config for www.42wide.com:

```nginx
location /food55/ {
    # Remove /food55 prefix before passing to app
    rewrite ^/food55/(.*)$ /$1 break;
    
    proxy_pass http://unix:/run/recipes-food55/recipes.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /food55;
}

location /food55/static/ {
    alias /var/www/recipes_remote/static/;
    expires 30d;
}
```

Reload nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## App Configuration for Subpath Deployment

If deploying to `/food55/`, the Flask app needs to know its base path. Modify `app.py`:

```python
# At the top of app.py, after Flask import:
from werkzeug.middleware.proxy_fix import ProxyFix

# After app = Flask(__name__):
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# For subpath support, update url_for and redirects:
APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '/food55')
app.config['APPLICATION_ROOT'] = APPLICATION_ROOT
```

Then update Jinja templates to use `url_for()` for all links (already done in current app).

---

## Database & Dependencies

### Update requirements.txt

Ensure this is on the server:

```
Flask>=2.0
gunicorn>=20.0
beautifulsoup4
requests
pytest>=9.0
```

Install with:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Verify Database is Copied

Ensure `recipes.db` is present on the server:

```bash
ls -la ~/recipes_remote/recipes.db
```

If not, copy it:

```bash
scp c:\Users\miket\Recipes_remote\recipes.db user@your.server.com:~/recipes_remote/
```

---

## SSL/HTTPS Setup (Recommended)

### For www.42wide.com (Cloudflare):

Cloudflare already provides SSL, so if you proxy to /food55, it should be encrypted automatically.

### For Your Own Server (Option A):

Use Let's Encrypt with certbot:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your.server.com
# Follow prompts

# Update nginx to use the certificate
sudo systemctl reload nginx
```

---

## Validation Checklist

After deployment, verify:

- [ ] `curl http://www.42wide.com/food55/` returns HTML search page
- [ ] Search functionality works
- [ ] Recipe detail pages load correctly
- [ ] Static files (CSS, images) load
- [ ] `/food55/static/` paths resolve correctly
- [ ] No 404 errors in nginx logs
- [ ] No permission errors on socket or database file

Check logs:

```bash
sudo journalctl -u recipes.service -n 50
sudo tail -f /var/log/nginx/error.log
```

---

## Rollback Plan

If something goes wrong:

1. **Disable the service:**
   ```bash
   sudo systemctl stop recipes.service
   sudo systemctl disable recipes.service
   ```

2. **Remove nginx location block** and reload:
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. **Food3 continues to work** (unaffected if on separate server)

---

## Next Steps

**Which option would you prefer?**

- **Option A:** Deploy to a separate public server, proxy via www.42wide.com/food55
- **Option B:** Deploy directly on the 42wide.com server

Let me know:
1. Whether you have a public server or just the www.42wide.com server
2. SSH access details (server IP, username)
3. Any existing web hosting/VPS provider you use

Then I can guide you through the actual deployment!
