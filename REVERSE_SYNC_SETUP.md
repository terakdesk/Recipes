# Reverse Sync Setup Guide

## Overview
The sync runs **FROM DreamHost (production)** and pushes changes **TO your local server (192.168.2.10)**.

This solves the authentication problem because DreamHost doesn't need to SSH back to itself - it just needs SSH access to your local server.

## Architecture
```
DreamHost (www.42wide.com/food55)  →  Your Local Server (192.168.2.10)
   ↓
Every day at 3 AM UTC
   ↓
DreamHost cron runs sync_production_to_local.sh
   ↓
Script SSH's to 192.168.2.10 using public key auth
   ↓
Pulls latest recipes.db and saved_recipes_json/
   ↓
Backs up local copies
   ↓
Replaces with production versions
   ↓
Restarts Flask on local server
```

## Prerequisites
Your local server (192.168.2.10):
- ✓ Running nginx with Flask app
- ✓ SSH server running (sshd)
- ✓ User `ethel` with password access
- ✓ Directory `/home/ethel/recipes_remote/` exists

## Step-by-Step Setup

### Step 1: Generate SSH Key ON DreamHost

**SSH to DreamHost as f42widec:**
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
```

**Generate SSH key pair for local server connection:**
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_local -N "" -C "f42widec@dreamhost-to-local-sync"
```

**Display the public key (copy this):**
```bash
cat ~/.ssh/id_rsa_local.pub
```

Output will look like:
```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCxxx... f42widec@dreamhost-to-local-sync
```

### Step 2: Add DreamHost Public Key to Local Server

**SSH to your local server from your Windows machine:**
```bash
ssh ethel@192.168.2.10
```

**Add DreamHost's public key to authorized_keys:**
```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Paste the public key from Step 1 into this file
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCxxx... f42widec@dreamhost-to-local-sync" >> ~/.ssh/authorized_keys

chmod 600 ~/.ssh/authorized_keys
```

**Verify the key was added:**
```bash
cat ~/.ssh/authorized_keys | grep dreamhost-to-local-sync
```

### Step 3: Test SSH Connection FROM DreamHost TO Local

**Back on DreamHost:**
```bash
# Test SSH connection (specify the private key)
ssh -i ~/.ssh/id_rsa_local ethel@192.168.2.10 "echo '✓ SSH connection working'"
```

Expected output:
```
✓ SSH connection working
```

### Step 4: Deploy Sync Script to DreamHost

**On your Windows machine, copy the reverse sync script:**
```bash
scp C:\Users\miket\Recipes_remote\sync_production_to_local_reverse.sh f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/sync_production_to_local.sh
```

**On DreamHost, make it executable:**
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "chmod +x ~/recipes_remote/sync_production_to_local.sh && echo '✓ Script deployed'"
```

### Step 5: Update SSH Config on DreamHost

The script needs to know which SSH key to use. **On DreamHost:**

```bash
cat > ~/.ssh/config << 'EOF'
Host 192.168.2.10
    HostName 192.168.2.10
    User ethel
    IdentityFile ~/.ssh/id_rsa_local
    StrictHostKeyChecking no
EOF

chmod 600 ~/.ssh/config
```

### Step 6: Test the Sync Script Manually

**On DreamHost, run the sync script manually first:**
```bash
~/recipes_remote/sync_production_to_local.sh
```

**Expected output:**
```
[2024-11-13 14:30:15] ================================================
[2024-11-13 14:30:15] Starting one-way sync: Production → Local
[2024-11-13 14:30:15] Production (here): /home/f42widec/recipes_remote
[2024-11-13 14:30:15] Local (remote): ethel@192.168.2.10:/home/ethel/recipes_remote
[2024-11-13 14:30:15] ================================================
[2024-11-13 14:30:15] Step 1: Checking local database...
[2024-11-13 14:30:15] ✓ Local database exists
...
[2024-11-13 14:30:45] ✓ One-way sync completed successfully!
```

**Check the log file:**
```bash
cat ~/recipes_remote/sync.log
```

**If something fails, check SSH manually:**
```bash
# This should connect without asking for password
ssh -i ~/.ssh/id_rsa_local ethel@192.168.2.10 "ls -la /home/ethel/recipes_remote/"
```

### Step 7: Schedule Sync in DreamHost Crontab

**Via DreamHost Control Panel (easiest):**
1. Log in to DreamHost control panel
2. Go to: Account → Billing & Account → Scheduled Tasks (or Cron Jobs)
3. Add new cron job:
   - Command: `/home/f42widec/recipes_remote/sync_production_to_local.sh`
   - Schedule: Daily at 3:00 AM (or your preferred time)
   - Email output: Yes (to receive sync logs)

**OR via SSH (if DreamHost control panel not available):**
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 3:00 AM UTC):
0 3 * * * /home/f42widec/recipes_remote/sync_production_to_local.sh >> /home/f42widec/recipes_remote/cron.log 2>&1
```

**Save and exit** (in vi editor: `:wq`)

### Step 8: Verify Cron Job

**Check if cron was added:**
```bash
crontab -l | grep sync_production
```

Should output:
```
0 3 * * * /home/f42widec/recipes_remote/sync_production_to_local.sh >> /home/f42widec/recipes_remote/cron.log 2>&1
```

**Check cron logs after first run:**
```bash
cat /home/f42widec/recipes_remote/cron.log
```

## Troubleshooting

### SSH Connection Fails
```bash
# Test SSH with verbose output
ssh -vvv -i ~/.ssh/id_rsa_local ethel@192.168.2.10

# Common issues:
# - Host key not accepted: Add to known_hosts
ssh-keyscan -t rsa 192.168.2.10 >> ~/.ssh/known_hosts

# - Permission denied: Check local authorized_keys
# - Host unreachable: Check if 192.168.2.10 is up
```

### Database Sync Fails
```bash
# Check if database exists on production
ls -lh ~/recipes_remote/recipes.db

# Check local server disk space
ssh ethel@192.168.2.10 "df -h /home/ethel/"

# Check local backup directory
ssh ethel@192.168.2.10 "ls -la /home/ethel/recipes_remote/sync_backups/"
```

### Flask Restart Fails
```bash
# Test Flask restart manually
ssh ethel@192.168.2.10 "cd /home/ethel/recipes_remote && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &"

# Check Flask status
ssh ethel@192.168.2.10 "ps aux | grep gunicorn"
```

### Script Runs but No Changes Appear
```bash
# Check sync log
cat ~/recipes_remote/sync.log

# Check if local server received files
ssh ethel@192.168.2.10 "ls -lh /home/ethel/recipes_remote/recipes.db"

# Check timestamps
stat ~/recipes_remote/recipes.db
```

## Files Created/Modified

**On DreamHost:**
- `~/.ssh/id_rsa_local` - Private key (keep secret!)
- `~/.ssh/id_rsa_local.pub` - Public key
- `~/.ssh/config` - SSH configuration
- `~/recipes_remote/sync_production_to_local.sh` - Sync script
- `~/recipes_remote/sync.log` - Sync logs
- `~/recipes_remote/cron.log` - Cron execution logs (if using crontab)

**On Local Server (192.168.2.10):**
- `~/.ssh/authorized_keys` - Added DreamHost public key
- `~/recipes_remote/sync_backups/` - Backup directory created
- `~/recipes_remote/recipes.db` - Updated with production version
- `~/recipes_remote/saved_recipes_json/` - Updated from production

## Daily Sync Verification

**After 3:00 AM UTC each day:**

Check DreamHost logs:
```bash
tail -20 ~/recipes_remote/sync.log
```

Verify local server received updates:
```bash
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/recipes.db && echo '' && ls -la ~/recipes_remote/sync_backups/ | head -5"
```

Check local Flask is running:
```bash
ssh ethel@192.168.2.10 "ps aux | grep gunicorn | grep -v grep"
```

## Security Notes

✓ SSH keys (RSA 4096-bit) are more secure than passwords
✓ Private key (`id_rsa_local`) stays only on DreamHost
✓ Public key is safe to share and goes only on local server
✓ No passwords stored anywhere
✓ Backups preserved before each sync
✓ All operations logged for audit trail

## Need Help?

If sync doesn't work after 3 AM:
1. Check `~/recipes_remote/sync.log` for errors
2. Check `~/recipes_remote/cron.log` for cron execution issues
3. Test SSH manually: `ssh -i ~/.ssh/id_rsa_local ethel@192.168.2.10`
4. Run script manually: `~/recipes_remote/sync_production_to_local.sh`

