# DreamHost Apache Configuration for www.42wide.com/food55

## Overview

DreamHost uses **Apache**, not nginx. Your Flask app runs on `127.0.0.1:8055`. We need to configure Apache to proxy requests from `www.42wide.com/food55` to your Flask app.

## Solution: Apache ProxyPass (via .htaccess)

### Option 1: Create a food55 subdirectory (Recommended)

This creates a cleaner structure:

**On DreamHost SSH:**

```bash
# Create the food55 directory structure
mkdir -p /home/f42widec/42wide.com/food55
```

**Then create `.htaccess` at `/home/f42widec/42wide.com/food55/.htaccess`:**

```bash
cat > /home/f42widec/42wide.com/food55/.htaccess << 'EOF'
# Enable Apache modules
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /food55/
    
    # Proxy all requests to Flask app on 127.0.0.1:8055
    RewriteCond %{HTTP_HOST} ^www\.42wide\.com$ [OR]
    RewriteCond %{HTTP_HOST} ^42wide\.com$
    RewriteRule ^(.*)$ http://127.0.0.1:8055/$1 [P,L]
</IfModule>

<IfModule mod_proxy.c>
    ProxyRequests Off
    ProxyPreserveHost On
    
    <Proxy http://127.0.0.1:8055/*>
        Allow from all
    </Proxy>
    
    ProxyPass / http://127.0.0.1:8055/
    ProxyPassReverse / http://127.0.0.1:8055/
</IfModule>
EOF

chmod 644 /home/f42widec/42wide.com/food55/.htaccess
```

### Option 2: Contact DreamHost Admin for VirtualHost Config

If Option 1 doesn't work, send this to DreamHost admin:

```
Please add this VirtualHost or location proxy configuration for www.42wide.com/food55:

    <Location /food55>
        ProxyPreserveHost On
        ProxyPass http://127.0.0.1:8055/
        ProxyPassReverse http://127.0.0.1:8055/
    </Location>
```

---

## Testing

### From Windows (PowerShell):

```powershell
curl http://www.42wide.com/food55/
```

Should return the Recipes search page HTML.

### From DreamHost SSH:

```bash
# Test that Flask is still running
ps -p $(cat /home/f42widec/recipes_remote/gunicorn.pid)

# Test local connection
curl http://127.0.0.1:8055/

# Check Apache error log for proxy issues
tail -50 /home/dhapache/logs/error.log
```

---

## Troubleshooting

### 502 Bad Gateway or Proxy Error

**Check if Flask app is running:**

```bash
ps aux | grep gunicorn
ps -p $(cat /home/f42widec/recipes_remote/gunicorn.pid)
```

If not running:

```bash
cd /home/f42widec/recipes_remote
nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
```

### Apache modules not enabled

DreamHost might require certain modules to be enabled. Contact admin if you see:

```
Cannot find proxy module
Cannot find rewrite module
```

Request them to enable `mod_proxy` and `mod_rewrite`.

### Permissions issue

Make sure `.htaccess` is readable:

```bash
ls -la /home/f42widec/42wide.com/food55/.htaccess
# Should show -rw-r--r--
chmod 644 /home/f42widec/42wide.com/food55/.htaccess
```

### Static files not loading

If CSS/JS doesn't load, the static directory path might need adjustment. Check:

```bash
ls -la /home/f42widec/recipes_remote/static/
# Should contain CSS, JS files
```

Update `.htaccess` if needed:

```
ProxyPass /static !
Alias /static /home/f42widec/recipes_remote/static/
```

---

## Keeping Flask App Running After Reboot

Add to crontab on DreamHost:

```bash
crontab -e
```

Add:

```
@reboot cd /home/f42widec/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &
```

---

## Summary

1. **Create `/home/f42widec/42wide.com/food55/` directory**
2. **Create `.htaccess` with ProxyPass config**
3. **Test**: `curl http://www.42wide.com/food55/`
4. **If issues**: Contact admin for VirtualHost help

Your Flask app should now be accessible at **www.42wide.com/food55/** 🚀
