# Production-to-Local Sync System

**Purpose:** Keep your local server (ethel@192.168.2.10) synchronized with production (www.42wide.com/food55)

**Sync Type:** One-way, one-direction pull: Production (DreamHost) → Local Server

---

## What This Does

✅ **Daily automatic sync** of recipes from production to local server
✅ **Detects changes:** New recipes and modifications on production
✅ **Safe:** Automatically backs up local database before replacing
✅ **Smart restart:** Flask restarted on local server to use new database
✅ **Logged:** All operations recorded for monitoring and troubleshooting

---

## Quick Start (5 Minutes)

### 1. Copy Script to Local Server
```bash
scp C:\Users\miket\Recipes_remote\sync_production_to_local.sh ethel@192.168.2.10:~/recipes_remote/
```

### 2. Make it Executable
```bash
ssh ethel@192.168.2.10 "chmod +x ~/recipes_remote/sync_production_to_local.sh"
```

### 3. Test It Once
```bash
ssh ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"
```

### 4. Check Results
```bash
ssh ethel@192.168.2.10 "tail -30 ~/recipes_remote/sync.log"
```

### 5. Schedule for Daily (3 AM)
```bash
ssh ethel@192.168.2.10 "echo '0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh' | crontab -"
```

**Done!** Your local server will now sync daily at 3 AM UTC.

---

## Files Included

### Main Script
- **`sync_production_to_local.sh`** - The sync script (copy to local server)

### Documentation
- **`SYNC_SETUP.md`** - Detailed setup and configuration guide
- **`SYNC_QUICK_REFERENCE.md`** - Quick commands and troubleshooting
- **`SYNC_README.md`** - This file

---

## How It Works

```
Every day at 3 AM UTC:
  1. Download recipes.db from production (DreamHost)
  2. Download saved_recipes_json/ from production
  3. Backup current local versions (timestamped)
  4. Replace local files with production versions
  5. Restart Flask on local server
  6. Log results to sync.log
```

---

## Key Features

### ✅ One-Way Sync (Safe)
- Only pulls from production, never pushes back
- Local changes won't overwrite production
- Perfect for read-only copy of production data

### ✅ Automatic Backups
- Every sync backs up your current database
- Backups timestamped for easy recovery
- Can restore any previous version anytime

### ✅ Connectivity Checks
- Verifies both servers are reachable before syncing
- Fails gracefully if either server is down
- Won't corrupt data if connection lost midway

### ✅ Comprehensive Logging
- Every action logged with timestamps
- Easy to troubleshoot if something fails
- Can monitor sync progress in real-time

### ✅ Automatic Flask Restart
- Flask restarted after database replacement
- New recipes immediately available
- No manual restart needed

---

## What Gets Synced

| Item | Synced? | Notes |
|------|---------|-------|
| `recipes.db` | ✅ Yes | Main database with all recipes |
| `saved_recipes_json/` | ✅ Yes | JSON backup of all recipes |
| Logs | ❌ No | (access.log, error.log, etc.) |
| Backups | ❌ No | (each server keeps its own) |
| Configuration | ❌ No | (each server keeps its settings) |
| Flask code | ❌ No | (must deploy separately) |

---

## Monitoring & Maintenance

### View Recent Syncs
```bash
ssh ethel@192.168.2.10 "tail -20 ~/recipes_remote/sync.log"
```

### Watch Sync in Real-Time
```bash
ssh ethel@192.168.2.10 "tail -f ~/recipes_remote/sync.log"
```

### List All Backups
```bash
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/sync_backups/"
```

### Check if Scheduled
```bash
ssh ethel@192.168.2.10 "crontab -l | grep sync"
```

---

## Troubleshooting

### Test Connectivity
```bash
# Test DreamHost
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "test -f /home/f42widec/recipes_remote/recipes.db && echo OK"

# Test Local
ssh ethel@192.168.2.10 "test -f ~/recipes_remote/recipes.db && echo OK"
```

### Sync Fails With "Permission Denied"
- Ensure SSH key access works
- Or use `ssh-keygen` to set up passwordless access

### Sync Fails With "Connection Timeout"
- Check network connectivity
- Verify servers are running
- Check firewall rules

### Sync Takes Too Long
- First run may take longer (many files)
- Subsequent runs are faster
- Check network bandwidth

### Need to Stop Syncing
```bash
ssh ethel@192.168.2.10 "crontab -e"
# Remove the sync line
```

### Restore From Backup
```bash
# List backups
ssh ethel@192.168.2.10 "ls -1 ~/recipes_remote/sync_backups/"

# Restore specific backup
ssh ethel@192.168.2.10 "cp ~/recipes_remote/sync_backups/recipes.db.backup_20261113_030000 ~/recipes_remote/recipes.db"

# Restart Flask
ssh ethel@192.168.2.10 "cd ~/recipes_remote && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &"
```

---

## Advanced Configuration

### Change Sync Time
Edit crontab on local server:
```bash
ssh ethel@192.168.2.10 "crontab -e"
```

Change the first line from:
```
0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh
```

To your preferred time (e.g., 6 AM):
```
0 6 * * * /home/ethel/recipes_remote/sync_production_to_local.sh
```

### Sync More Frequently
For every 12 hours:
```bash
ssh ethel@192.168.2.10 "echo '0 */12 * * * /home/ethel/recipes_remote/sync_production_to_local.sh' | crontab -"
```

### Setup SSH Keys (Passwordless)
```bash
# Generate key
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\dreamhost_recipes

# Copy to DreamHost
type $env:USERPROFILE\.ssh\dreamhost_recipes.pub | ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cat >> ~/.ssh/authorized_keys"
```

---

## Safety & Reliability

### Backups
✅ Automatic timestamped backups before each sync
✅ Can restore from any previous backup
✅ Backups kept indefinitely (clean up manually as needed)

### Verification
✅ Script checks connectivity to both servers first
✅ Only proceeds if both servers reachable
✅ Backs up local data before making changes

### Rollback
✅ Can restore from backup anytime
✅ No data loss possible (always backed up first)
✅ Simple one-command restore

---

## Data Flow Example

**Before Sync:**
```
Production:  recipes.db (809 recipes, modified today)
Local:       recipes.db (809 recipes, modified yesterday)
```

**After Sync:**
```
Production:  recipes.db (unchanged)
Local:       recipes.db (updated, now same as production)
Backup:      recipes.db.backup_20261113_030000 (yesterday's version)
```

---

## Statistics

| Metric | Details |
|--------|---------|
| Sync Time | ~2-5 minutes (after first run) |
| Data Size | ~4 MB database + ~20 MB JSON files |
| Storage | Backups use ~4 MB per sync |
| Frequency | Daily recommended |
| Errors | Fails safely if connectivity issue |

---

## Summary

You now have:

✅ **One-way sync script** that pulls production data to local server
✅ **Automatic daily scheduling** via cron (3 AM UTC)
✅ **Timestamped backups** of your local data before each sync
✅ **Automatic Flask restart** to use new database
✅ **Complete logging** for monitoring and troubleshooting
✅ **Easy recovery** - can restore any backup anytime

**To start:** Follow the "Quick Start" section above!

---

## Support

- **Full documentation:** See `SYNC_SETUP.md`
- **Quick commands:** See `SYNC_QUICK_REFERENCE.md`
- **Log file:** `/home/ethel/recipes_remote/sync.log`
- **Backups:** `/home/ethel/recipes_remote/sync_backups/`

---

**Last Updated:** November 13, 2026
**Created by:** Copilot AI Assistant
