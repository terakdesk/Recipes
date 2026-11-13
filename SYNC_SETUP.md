# Production-to-Local Sync Setup

**Objective:** One-way sync from production (www.42wide.com/food55) to local (ethel@192.168.2.10)

**Sync Direction:** DreamHost Production → Local Server (Master → Replica)

---

## Overview

The sync script automatically:
1. ✅ Downloads `recipes.db` from production
2. ✅ Downloads `saved_recipes_json/` from production
3. ✅ Backs up your local versions (timestamped)
4. ✅ Replaces local files with production versions
5. ✅ Restarts Flask on local server
6. ✅ Logs all operations

**What it syncs:**
- Database (recipes.db)
- Recipe JSON files (saved_recipes_json/)

**What it does NOT sync:**
- Logs (access.log, error.log, restart.log, etc.)
- Backups directory
- Environment configuration
- User data (only replaces recipes)

---

## Installation

### Step 1: Copy Script to Local Server

Copy `sync_production_to_local.sh` to your local server:

```bash
# On your Windows machine with SSH access
scp C:\Users\miket\Recipes_remote\sync_production_to_local.sh ethel@192.168.2.10:~/recipes_remote/

# Or manually place it in /home/ethel/recipes_remote/
```

### Step 2: Make Script Executable

On local server:
```bash
ssh ethel@192.168.2.10
chmod +x ~/recipes_remote/sync_production_to_local.sh
exit
```

### Step 3: Test the Script Manually

```bash
# Run once to test
ssh ethel@192.168.2.10 "~/recipes_remote/sync_production_to_local.sh"

# Check the log
ssh ethel@192.168.2.10 "tail -50 ~/recipes_remote/sync.log"
```

Expected output:
```
[2026-11-13 12:00:00] ================================================
[2026-11-13 12:00:00] Starting one-way sync: Production → Local
[2026-11-13 12:00:00] Production: f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote
[2026-11-13 12:00:00] Local: ethel@192.168.2.10:/home/ethel/recipes_remote
[2026-11-13 12:00:00] ================================================
[2026-11-13 12:00:05] SUCCESS: Connected to production server
[2026-11-13 12:00:10] SUCCESS: Connected to local server
...
[2026-11-13 12:00:45] SUCCESS: One-way sync completed successfully!
```

---

## Automated Daily Sync

### Option A: Add to Local Server Crontab (Recommended)

SSH into local server and edit crontab:

```bash
ssh ethel@192.168.2.10
crontab -e

# Add this line (syncs daily at 3 AM):
0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh

# Save and exit
```

### Option B: Add to Windows Task Scheduler

Create a scheduled task on your Windows machine:

```powershell
# Run as Administrator
$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM
$action = New-ScheduledTaskAction -Execute "ssh" -Argument 'ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"'
Register-ScheduledTask -TaskName "SyncRecipesFromProduction" -Trigger $trigger -Action $action
```

### Option C: Manual Schedule with Windows Task Scheduler GUI

1. Open Task Scheduler
2. Create Basic Task
3. **Name:** "Sync Recipes from Production"
4. **Trigger:** Daily at 3:00 AM
5. **Action:** Start a program
   - Program: `C:\Windows\System32\ssh.exe`
   - Arguments: `ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"`

---

## Monitoring Syncs

### View Recent Syncs

```bash
# Last 20 sync log entries
ssh ethel@192.168.2.10 "tail -20 ~/recipes_remote/sync.log"

# Last 50 sync log entries
ssh ethel@192.168.2.10 "tail -50 ~/recipes_remote/sync.log"

# Watch sync logs in real-time (useful during first run)
ssh ethel@192.168.2.10 "tail -f ~/recipes_remote/sync.log"
```

### List Backups

```bash
# See all timestamped backups
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/sync_backups/"

# Most recent backup
ssh ethel@192.168.2.10 "ls -lht ~/recipes_remote/sync_backups/ | head -1"
```

### Restore from Backup

If you need to restore a previous version:

```bash
# List backups
ssh ethel@192.168.2.10 "ls -1 ~/recipes_remote/sync_backups/recipes.db.backup_*"

# Restore specific backup (replace TIMESTAMP with your backup date)
ssh ethel@192.168.2.10 "cp ~/recipes_remote/sync_backups/recipes.db.backup_20261113_030000 ~/recipes_remote/recipes.db"

# Restart Flask
ssh ethel@192.168.2.10 "cd ~/recipes_remote && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &"
```

---

## Troubleshooting

### "Cannot connect to production server"

Check if DreamHost server is reachable:
```bash
ssh -v f42widec@pdx1-shared-a3-07.dreamhost.com "echo OK"
```

### "Cannot connect to local server"

Check if local server is reachable:
```bash
ssh -v ethel@192.168.2.10 "echo OK"
```

### "rsync not available"

The script automatically falls back to `scp` if `rsync` is not available. This is slower but will work.

### "Failed to backup local database"

Ensure you have enough disk space:
```bash
ssh ethel@192.168.2.10 "df -h /home/ethel/"
```

### Sync Takes Too Long

The first sync might take longer if there are many JSON files. Subsequent syncs are faster.

To see progress:
```bash
ssh ethel@192.168.2.10 "tail -f ~/recipes_remote/sync.log"
```

---

## SSH Key Setup (Optional - for Passwordless Access)

If you get prompted for passwords during sync, set up SSH keys for passwordless access:

### From Windows to DreamHost:

```bash
# Generate key (if you don't have one)
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\dreamhost_recipes

# Copy public key to DreamHost
type $env:USERPROFILE\.ssh\dreamhost_recipes.pub | ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cat >> ~/.ssh/authorized_keys"

# Test
ssh -i $env:USERPROFILE\.ssh\dreamhost_recipes f42widec@pdx1-shared-a3-07.dreamhost.com "echo OK"
```

### From Local Server to Local Server (should already be set up):

Usually no need since they're on same network.

---

## Sync Schedule Recommendations

| Frequency | Crontab | Use Case |
|-----------|---------|----------|
| Daily at 3 AM | `0 3 * * *` | Default (gives time for automated backups) |
| Daily at 6 AM | `0 6 * * *` | If you edit recipes at night |
| Every 12 hours | `0 */12 * * *` | High frequency changes |
| Every 6 hours | `0 */6 * * *` | Very frequent changes |
| Weekly (Monday 3 AM) | `0 3 * * 1` | Weekly sync (low-frequency server) |

---

## Dry Run (Test Without Changing Files)

To test the sync without actually changing files:

```bash
# Edit the script and add --dry-run to rsync commands
# Or modify the last step to NOT restart Flask

# Run with dry-run
ssh ethel@192.168.2.10 "bash -x ~/recipes_remote/sync_production_to_local.sh 2>&1 | tail -100"
```

---

## Sync Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Daily Cron Job (3 AM UTC)                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Check Connectivity         │
        │ - Production (DreamHost)   │
        │ - Local (192.168.2.10)     │
        └────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Backup Local Database      │
        │ → sync_backups/            │
        │ (timestamped)              │
        └────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Download Production Data   │
        │ - recipes.db               │
        │ - saved_recipes_json/      │
        └────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Upload to Local Server     │
        │ - recipes.db               │
        │ - saved_recipes_json/      │
        └────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Restart Flask on Local     │
        │ (picks up new database)    │
        └────────────┬───────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ Log Results to sync.log    │
        │ - Success/failure          │
        │ - Backup location          │
        │ - File sizes               │
        └────────────────────────────┘
```

---

## Backup Retention

The script keeps all timestamped backups. Over time, these will accumulate. To clean up old backups:

```bash
# Keep only last 10 backups
ssh ethel@192.168.2.10 "cd ~/recipes_remote/sync_backups && ls -1t recipes.db.backup_* | tail -n +11 | xargs rm -f"

# Or manually delete specific backup
ssh ethel@192.168.2.10 "rm ~/recipes_remote/sync_backups/recipes.db.backup_20261101_030000"
```

---

## Verification Checklist

After first sync, verify everything worked:

- [ ] Local database is up to date
- [ ] Recipe count matches (809)
- [ ] Recent recipes appear in local app
- [ ] Log shows "SUCCESS" message
- [ ] Backup file was created
- [ ] Cron job is scheduled (if using automatic sync)
- [ ] Flask restarted without errors

Quick test:

```bash
# Check recipe count on local server
ssh ethel@192.168.2.10 "sqlite3 ~/recipes_remote/recipes.db 'SELECT COUNT(*) FROM recipes WHERE is_valid = 1;'"

# Expected output: 809 (or current count)
```

---

## Disaster Recovery

If something goes wrong during sync:

1. **Local server database corrupted?**
   ```bash
   ssh ethel@192.168.2.10 "cp ~/recipes_remote/sync_backups/recipes.db.backup_TIMESTAMP ~/recipes_remote/recipes.db"
   ssh ethel@192.168.2.10 "cd ~/recipes_remote && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &"
   ```

2. **Need to stop all syncs?**
   ```bash
   # Remove from crontab
   ssh ethel@192.168.2.10 "crontab -e"
   # Delete the sync line
   ```

3. **Manually run sync anytime:**
   ```bash
   ssh ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"
   ```

---

## Support & Questions

- **Log location:** `/home/ethel/recipes_remote/sync.log`
- **Backups location:** `/home/ethel/recipes_remote/sync_backups/`
- **Script location:** `/home/ethel/recipes_remote/sync_production_to_local.sh`

Check the sync log for detailed error messages if something fails:
```bash
ssh ethel@192.168.2.10 "tail -100 ~/recipes_remote/sync.log | grep -i error"
```
