# Manual DreamHost Deployment - Step by Step

## Quick Deployment (Copy & Paste Commands)

Open **PowerShell** and run these commands one by one. When prompted for password, enter your SSH password.

### Step 1: Copy app files

```powershell
$user = "f42widec"
$host = "pdx1-shared-a3-07.dreamhost.com"
$dest = "$user@$host`:~/recipes_remote/"

# Create directory first
ssh $user@$host "mkdir -p ~/recipes_remote"

# Copy files
scp c:\Users\miket\Recipes_remote\app.py $dest
scp c:\Users\miket\Recipes_remote\recipes.db $dest
scp c:\Users\miket\Recipes_remote\requirements.txt $dest
scp c:\Users\miket\Recipes_remote\filtered_tags.py $dest
scp c:\Users\miket\Recipes_remote\dreamhost_deploy.sh $dest
```

**Expected:** 5 files copied, password prompted for each

### Step 2: Copy directories

```powershell
$user = "f42widec"
$host = "pdx1-shared-a3-07.dreamhost.com"
$dest = "$user@$host`:~/recipes_remote/"

scp -r c:\Users\miket\Recipes_remote\templates $dest
scp -r c:\Users\miket\Recipes_remote\static $dest
scp -r c:\Users\miket\Recipes_remote\saved_recipes_json $dest
```

**Expected:** 3 directories copied (this takes 1-2 minutes)

### Step 3: SSH and run deployment

```powershell
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
```

**In SSH session:**

```bash
cd ~/recipes_remote
bash dreamhost_deploy.sh
```

**Wait for output:** `✅ DEPLOYMENT COMPLETE!`

### Step 4: Start the app

**Still in SSH session:**

```bash
cd ~/recipes_remote
nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
sleep 3
ps -p $(cat gunicorn.pid) && echo "✅ App running" || echo "❌ App failed"
```

**Expected output:** `✅ App running`

### Step 5: Verify it's listening

**Still in SSH session:**

```bash
ss -tuln | grep 8055
```

**Expected output:** Something like:
```
tcp  LISTEN  0  128  127.0.0.1:8055  0.0.0.0:*
```

### Step 6: Exit SSH and contact admin

```bash
exit
```

---

## Admin Request Template

Send this to DreamHost support:

```
Hello,

I have a Flask app running on localhost port 8055 (user: f42widec).

Please add this to the nginx config for www.42wide.com:

---BEGIN NGINX CONFIG---

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

---END NGINX CONFIG---

After adding, please run:
  nginx -t
  systemctl reload nginx

Let me know when it's live. Thanks!
```

---

## After Admin Confirms

Once admin says it's configured, test:

```powershell
curl http://www.42wide.com/food55/
```

Or open in browser: **http://www.42wide.com/food55/**

You should see the Recipes search page! 🎉

---

## Troubleshooting

### Check if app is still running

```powershell
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
ps -p $(cat ~/recipes_remote/gunicorn.pid)
```

If not running, restart:

```bash
cd ~/recipes_remote
nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
```

### View error logs

```bash
tail -50 ~/recipes_remote/error.log
tail -50 ~/recipes_remote/gunicorn.log
```

### Test locally on server

```bash
curl http://127.0.0.1:8055/
```

Should return HTML page.

---

## Done!

Your Recipes app is now deployed to www.42wide.com/food55! 🚀
