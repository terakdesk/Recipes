# 🚀 Quick DreamHost Deployment Checklist

## Summary
Deploy your Recipes Flask app to www.42wide.com/food55 on DreamHost shared hosting.

**Server:** pdx1-shared-a3-07.dreamhost.com  
**User:** f42widec  
**Password:** ✓ (saved)

---

## ✅ Phase 1: Copy Files (Windows Machine)

Run in PowerShell:

```powershell
$user = "f42widec"
$host = "pdx1-shared-a3-07.dreamhost.com"

# Create remote directory first
ssh $user@$host "mkdir -p ~/recipes_remote"

# Copy files (you'll be prompted for password)
scp c:\Users\miket\Recipes_remote\app.py $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\recipes.db $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\requirements.txt $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\filtered_tags.py $user@$host:~/recipes_remote/
scp c:\Users\miket\Recipes_remote\dreamhost_deploy.sh $user@$host:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\templates $user@$host:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\static $user@$host:~/recipes_remote/
scp -r c:\Users\miket\Recipes_remote\saved_recipes_json $user@$host:~/recipes_remote/

Write-Host "✅ All files copied!"
```

**Note:** When prompted for password, enter your SSH password.

---

## ✅ Phase 2: SSH In and Deploy

Open PowerShell or any SSH client:

```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
# Enter password when prompted
```

Once connected:

```bash
cd ~/recipes_remote
bash dreamhost_deploy.sh
```

**Wait for output that says:** ✅ DEPLOYMENT COMPLETE!

**Important:** Save the Flask Secret Key that's displayed

---

## ✅ Phase 3: Start the App

Still in SSH session:

```bash
cd ~/recipes_remote
nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
sleep 3

# Verify it's running
ps -p $(cat gunicorn.pid) && echo "✅ App is running!" || echo "❌ App failed to start"

# Test it locally
curl http://127.0.0.1:8055/
```

If you see HTML output, the app is working!

---

## ✅ Phase 4: Contact DreamHost Admin

Send this message to DreamHost support:

```
Please add this nginx configuration for www.42wide.com/food55:

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

After adding, please run: nginx -t && systemctl reload nginx
```

**Then wait for confirmation.**

---

## ✅ Phase 5: Test the Live Site

Once admin confirms nginx is configured, test:

```powershell
# From Windows PowerShell
curl http://www.42wide.com/food55/
```

Or open in browser: **http://www.42wide.com/food55/**

You should see the Recipes search page! 🎉

---

## ✅ Phase 6: Set Up Persistent Running

Back in SSH session, make app survive server reboots:

```bash
# Add to crontab
crontab -e

# Add this line:
@reboot cd $HOME/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &

# Save and exit (Ctrl+X then Y in nano)
```

---

## ⚠️ If Anything Goes Wrong

### App won't start
```bash
tail -50 ~/recipes_remote/error.log
```

### Port 8055 not responding
```bash
ss -tuln | grep 8055
ps aux | grep gunicorn
```

### Need to restart app
```bash
kill $(cat ~/recipes_remote/gunicorn.pid)
cd ~/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 &
echo $! > gunicorn.pid
```

### nginx says 502 Bad Gateway
- App crashed: check error.log
- Port not listening: `ss -tuln | grep 8055`
- Check admin configured nginx correctly

---

## 📋 Checklist

- [ ] Downloaded/created all files locally
- [ ] Created ~/recipes_remote/ on DreamHost
- [ ] Copied all files via scp (app.py, recipes.db, templates/, static/, etc.)
- [ ] Ran `bash dreamhost_deploy.sh` successfully
- [ ] Started app with `nohup ./start.sh`
- [ ] Verified local access: `curl http://127.0.0.1:8055/`
- [ ] Saved Flask Secret Key
- [ ] Contacted DreamHost admin about nginx config
- [ ] Admin confirmed /food55 location blocks added
- [ ] Tested www.42wide.com/food55 in browser
- [ ] Added crontab entry for auto-restart

---

## 📞 Support Commands

Save these for quick reference:

```bash
# SSH in
ssh f42widec@pdx1-shared-a3-07.dreamhost.com

# Status check
cd ~/recipes_remote
ps -p $(cat gunicorn.pid) && echo "Running" || echo "Down"

# View errors
tail -f error.log

# Restart
kill $(cat gunicorn.pid) 2>/dev/null; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 & echo $! > gunicorn.pid

# Stop
kill $(cat gunicorn.pid); rm gunicorn.pid
```

---

## 🎯 End Result

When complete, you'll have:
- ✅ Recipes app running at www.42wide.com/food55
- ✅ Full recipe search, browse, and view functionality
- ✅ 809 recipes from local copy
- ✅ App auto-restarts on server reboot
- ✅ Admin monitors app health

**Time to deploy:** ~20 minutes (excluding admin nginx config time)

Good luck! 🚀
