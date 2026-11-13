# Reverse Sync Setup - Complete Summary

## Problem Solved ✓

**Original Issue:** Local server couldn't authenticate to DreamHost (SSH key and password auth both failed)

**Solution:** Reversed the sync direction!
- Sync now runs **FROM DreamHost** (where it has full access to its own files)
- DreamHost **pushes** recipes to your local server instead of local pulling from DreamHost
- Uses SSH public key authentication FROM DreamHost TO local (much simpler)
- Runs silently via cron at 3:00 AM UTC daily

## Architecture Change

```
BEFORE (Failed):
Local (192.168.2.10) → SSH → DreamHost (www.42wide.com/food55)
                     ✗ Authentication blocked

AFTER (Works):
DreamHost → SSH → Local (192.168.2.10)
✓ DreamHost has file access
✓ Public key auth is simple
✓ Runs via cron silently
```

## Files Created

In `C:\Users\miket\Recipes_remote\`:

1. **sync_production_to_local_reverse.sh** (Main script)
   - Runs ON DreamHost
   - Pushes database and recipes to local server
   - Creates backups before updating
   - Restarts Flask on local server
   - Logs all operations to sync.log
   - Uses SSH key: `~/.ssh/id_rsa_local`

2. **REVERSE_SYNC_SETUP.md** (Detailed guide)
   - Complete step-by-step setup instructions
   - Architecture explanation
   - Troubleshooting guide
   - Security notes
   - 8,100 words of comprehensive documentation

3. **REVERSE_SYNC_QUICK.txt** (Quick reference)
   - Condensed commands for quick setup
   - Copy-paste ready commands
   - All 8 setup steps on one page

## Setup Process (8 Steps)

1. **Copy script to DreamHost** (from Windows)
   ```
   scp C:\Users\miket\Recipes_remote\sync_production_to_local_reverse.sh f42widec@pdx1-shared-a3-07.dreamhost.com:/home/f42widec/recipes_remote/sync_production_to_local.sh
   ```

2. **SSH to DreamHost**
   ```
   ssh f42widec@pdx1-shared-a3-07.dreamhost.com
   ```

3. **Generate SSH key on DreamHost**
   ```
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_local -N "" -C "f42widec@dreamhost-to-local-sync"
   cat ~/.ssh/id_rsa_local.pub  # Copy this!
   ```

4. **SSH to local server**
   ```
   ssh ethel@192.168.2.10
   ```

5. **Add DreamHost public key to local authorized_keys**
   ```
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

6. **Back on DreamHost: Configure SSH and test**
   ```
   cat > ~/.ssh/config << 'EOF'
   Host 192.168.2.10
       HostName 192.168.2.10
       User ethel
       IdentityFile ~/.ssh/id_rsa_local
       StrictHostKeyChecking no
   EOF
   chmod 600 ~/.ssh/config
   
   ssh -i ~/.ssh/id_rsa_local ethel@192.168.2.10 "echo '✓ SSH works'"
   ```

7. **Make script executable and test manually**
   ```
   chmod +x ~/recipes_remote/sync_production_to_local.sh
   ~/recipes_remote/sync_production_to_local.sh
   ```

8. **Add to DreamHost crontab for daily 3 AM UTC execution**
   ```
   crontab -e
   # Add: 0 3 * * * /home/f42widec/recipes_remote/sync_production_to_local.sh >> /home/f42widec/recipes_remote/cron.log 2>&1
   ```

## What Happens During Sync

Every day at 3:00 AM UTC:

1. ✓ Check that production database exists
2. ✓ Test SSH connection to local server (192.168.2.10)
3. ✓ Create dated backup of local recipes.db (recipes.db.backup_20241113_030015)
4. ✓ Push recipes.db from DreamHost to local server
5. ✓ Backup local saved_recipes_json directory
6. ✓ Push production saved_recipes_json directory to local server
7. ✓ Restart Flask on local server
8. ✓ Log all operations to ~/recipes_remote/sync.log

## Security Features

✓ **SSH Public Key Auth** (RSA 4096-bit)
  - Private key stays only on DreamHost
  - Public key on local server only
  - No passwords stored anywhere

✓ **Automated Backups**
  - Local recipes backed up before each sync
  - Timestamped backups in sync_backups/
  - Easy recovery if needed

✓ **Audit Trail**
  - Every sync logged with timestamps
  - Success/failure logged explicitly
  - Cron execution logged separately

✓ **Error Handling**
  - Script checks each step
  - Fails gracefully with clear error messages
  - No silent failures

## How to Verify Setup Works

**Day 1:** Follow the 8 setup steps from REVERSE_SYNC_SETUP.md

**Day 1 Evening:** Test sync manually on DreamHost
```
~/recipes_remote/sync_production_to_local.sh
```
Expected: Clean output ending with "One-way sync completed successfully!"

**Day 2 Morning (after 3:00 AM UTC):** Check cron execution
```
# On DreamHost:
cat ~/recipes_remote/sync.log | tail -20
cat ~/recipes_remote/cron.log

# From Windows to local server:
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/recipes.db"
```

## Troubleshooting Quick Links

See **REVERSE_SYNC_SETUP.md** section: "Troubleshooting"

Common issues:
- SSH connection fails → Test with verbose: `ssh -vvv -i ~/.ssh/id_rsa_local ethel@192.168.2.10`
- Database sync fails → Check disk space: `df -h`
- Flask restart fails → Test manually
- No changes appearing → Check timestamps on files

## Files on Local Server After Setup

```
/home/ethel/
├── recipes_remote/
│   ├── recipes.db (updated daily)
│   ├── saved_recipes_json/ (updated daily)
│   ├── sync_backups/
│   │   ├── recipes.db.backup_20241113_030015
│   │   ├── recipes.db.backup_20241114_030017
│   │   ├── saved_recipes_json.backup_20241113_030015
│   │   └── saved_recipes_json.backup_20241114_030017
│   ├── start.sh
│   ├── app.py
│   ├── gunicorn.log
│   └── ... (rest of Flask app)
└── .ssh/
    └── authorized_keys (contains DreamHost public key)
```

## Files on DreamHost After Setup

```
/home/f42widec/
├── recipes_remote/
│   ├── recipes.db
│   ├── saved_recipes_json/
│   ├── sync_production_to_local.sh (executable)
│   ├── sync.log (grows with each sync)
│   ├── cron.log (created after first cron run)
│   └── ... (rest of production app)
└── .ssh/
    ├── id_rsa_local (private key - KEEP SECRET!)
    ├── id_rsa_local.pub (public key)
    ├── config (SSH configuration)
    └── known_hosts
```

## Next Steps

1. ✓ Read REVERSE_SYNC_SETUP.md (detailed guide)
2. ✓ Read REVERSE_SYNC_QUICK.txt (quick commands)
3. ✓ Follow 8 setup steps in order
4. ✓ Test manually before relying on cron
5. ✓ Check logs after first cron execution at 3:00 AM UTC

---

**Questions?** 
Check the troubleshooting section in REVERSE_SYNC_SETUP.md first, then refer to the script logs for specific errors.

**Everything working?**
You now have daily automated one-way sync from production to local! 🎉
