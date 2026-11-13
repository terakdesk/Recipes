# REVERSE SYNC SYSTEM - FILE INDEX & NAVIGATION

## Overview

This package contains everything needed to set up daily automated synchronization of recipes from your production server (DreamHost at www.42wide.com/food55) to your local server (ethel@192.168.2.10).

**Key Change:** Sync runs FROM DreamHost pushing TO local, instead of local pulling from DreamHost. This solves all authentication issues!

---

## File Guide

### For Getting Started (Read These First)

1. **REVERSE_SYNC_SUMMARY.md** ⭐ START HERE
   - 5-minute overview of the solution
   - Lists all 8 setup steps
   - Explains what happens during sync
   - Shows security features
   - File: `C:\Users\miket\Recipes_remote\REVERSE_SYNC_SUMMARY.md`

2. **REVERSE_SYNC_QUICK.txt** ⭐ USE FOR QUICK SETUP
   - One-page reference with all commands
   - Copy-paste ready for each step
   - Perfect for following along
   - File: `C:\Users\miket\Recipes_remote\REVERSE_SYNC_QUICK.txt`

### For Detailed Information

3. **REVERSE_SYNC_SETUP.md** (Comprehensive Guide)
   - 40+ sections covering every detail
   - Step-by-step setup with explanations
   - Detailed troubleshooting guide
   - Security best practices
   - File: `C:\Users\miket\Recipes_remote\REVERSE_SYNC_SETUP.md`

4. **REVERSE_SYNC_ARCHITECTURE.txt** (Visual Diagrams)
   - System architecture diagrams
   - Network flow diagrams
   - SSH authentication flow
   - Backup strategy visualization
   - Monitoring checklist
   - File: `C:\Users\miket\Recipes_remote\REVERSE_SYNC_ARCHITECTURE.txt`

### The Actual Script (Deploy This)

5. **sync_production_to_local_reverse.sh** (Main Script)
   - 150+ lines of bash script
   - Runs ON DreamHost production server
   - Handles all sync operations
   - Includes error checking and logging
   - Deploy to: `/home/f42widec/recipes_remote/sync_production_to_local.sh`
   - File: `C:\Users\miket\Recipes_remote\sync_production_to_local_reverse.sh`

---

## Which File to Read When

### "I'm ready to set up - what do I do?"
→ Read **REVERSE_SYNC_QUICK.txt** first
→ Copy-paste commands one by one
→ Refer to **REVERSE_SYNC_SETUP.md** if questions arise

### "I want to understand the system architecture"
→ Read **REVERSE_SYNC_SUMMARY.md** for overview
→ Read **REVERSE_SYNC_ARCHITECTURE.txt** for diagrams
→ Then follow **REVERSE_SYNC_QUICK.txt** for setup

### "Setup failed - how do I fix it?"
→ Check **REVERSE_SYNC_SETUP.md** section: "Troubleshooting"
→ Look up your specific error
→ Verify SSH connection with provided test commands

### "I need to understand every detail"
→ Read **REVERSE_SYNC_SETUP.md** completely
→ It covers every aspect with explanations
→ Includes all edge cases and security notes

### "Just give me the commands"
→ Use **REVERSE_SYNC_QUICK.txt** exclusively
→ It's distilled to essential steps only
→ All copy-paste ready

---

## Setup Flow Chart

```
START
  ↓
Read: REVERSE_SYNC_SUMMARY.md (5 minutes)
  ↓
Read: REVERSE_SYNC_QUICK.txt (1 minute scan)
  ↓
Follow: REVERSE_SYNC_QUICK.txt (steps 1-8)
  ↓
Test: Run script manually on DreamHost
  ↓
Add: Cron job on DreamHost
  ↓
Verify: Check logs after 3 AM UTC next day
  ↓
DONE - Daily sync running!
```

---

## Key Concepts Explained

### What is "Reverse Sync"?

Instead of:
```
Local Server (192.168.2.10) → SSH → DreamHost (production)
                            ✗ Authentication blocked
```

We do:
```
DreamHost (production) → SSH → Local Server (192.168.2.10)
                       ✓ Public key auth works
```

### Why Does This Work?

- DreamHost script has **direct access** to its own files (no SSH needed for that)
- DreamHost script uses **public key authentication** to connect to local server (much simpler)
- Local server just needs to allow SSH connections (it already does)
- No passwords stored anywhere (security!)

### How Often Does It Sync?

**Every day at 3:00 AM UTC**

Via DreamHost crontab:
```
0 3 * * * /home/f42widec/recipes_remote/sync_production_to_local.sh
```

### What Gets Synced?

1. **recipes.db** - The database (809 recipes)
   - Copied from DreamHost to local server
   - Backed up locally before update

2. **saved_recipes_json/** - Individual recipe files
   - Entire directory copied
   - Backed up locally before update

### What About Backups?

✓ **Before each sync**, local server backs up:
  - `recipes.db` → `sync_backups/recipes.db.backup_20241113_030015`
  - `saved_recipes_json/` → `sync_backups/saved_recipes_json.backup_20241113_030015`

✓ Full history preserved in `~/recipes_remote/sync_backups/`
✓ Easy recovery if needed

---

## Quick Reference

### File Locations

| Server | Path | Purpose |
|--------|------|---------|
| DreamHost | `~/.ssh/id_rsa_local` | Private SSH key |
| DreamHost | `~/.ssh/id_rsa_local.pub` | Public SSH key |
| DreamHost | `~/.ssh/config` | SSH configuration |
| DreamHost | `~/recipes_remote/sync_production_to_local.sh` | Sync script |
| DreamHost | `~/recipes_remote/sync.log` | Sync execution log |
| Local | `~/.ssh/authorized_keys` | Contains DreamHost public key |
| Local | `~/recipes_remote/recipes.db` | Synced database |
| Local | `~/recipes_remote/saved_recipes_json/` | Synced recipes |
| Local | `~/recipes_remote/sync_backups/` | Backup storage |
| Windows | `C:\Users\miket\Recipes_remote\*` | Documentation & scripts |

### Key Commands

```bash
# SSH to DreamHost production
ssh f42widec@pdx1-shared-a3-07.dreamhost.com

# SSH to local server
ssh ethel@192.168.2.10

# Test sync manually (on DreamHost)
~/recipes_remote/sync_production_to_local.sh

# Check sync log (on DreamHost)
tail -20 ~/recipes_remote/sync.log

# Verify local received update (from Windows)
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/recipes.db"

# Check if Flask is running (from Windows)
ssh ethel@192.168.2.10 "ps aux | grep gunicorn | grep -v grep"

# See backup history (on DreamHost)
ls -lt ~/recipes_remote/sync_backups/ | head -10
```

---

## Prerequisites Checklist

Before starting setup, verify you have:

- [ ] DreamHost shell access (SSH to pdx1-shared-a3-07.dreamhost.com)
- [ ] Local server SSH access (SSH to ethel@192.168.2.10)
- [ ] Local server directory exists: `/home/ethel/recipes_remote/`
- [ ] Production directory exists: `/home/f42widec/recipes_remote/recipes.db`
- [ ] At least 1 GB disk space on local server
- [ ] Flask/Gunicorn running on local server
- [ ] Your Windows machine with PowerShell/Git Bash

---

## Common Questions

**Q: Do I need to do this setup on my Windows machine?**
A: No, your Windows machine is only used for deploying the script TO DreamHost. All setup (steps 2-8) happens on DreamHost or local server via SSH.

**Q: What if I miss the 3 AM sync window?**
A: No problem! You can run the sync manually any time:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
~/recipes_remote/sync_production_to_local.sh
```

**Q: Can I change the 3 AM sync time?**
A: Yes! Edit the crontab on DreamHost:
```bash
crontab -e
# Change: 0 3 * * * ...
#    To: 0 10 * * * ... (for 10 AM UTC instead)
```

**Q: What if the sync fails?**
A: Check the logs:
```bash
# On DreamHost:
tail -50 ~/recipes_remote/sync.log
cat ~/recipes_remote/cron.log
```
Refer to "Troubleshooting" section in REVERSE_SYNC_SETUP.md

**Q: Are my recipes safe?**
A: Yes! Before each sync:
- Local recipes backed up with timestamp
- Script checks all steps before proceeding
- All operations logged for audit trail
- Easy recovery from sync_backups/ directory

---

## Support Resources

| Issue | File to Check |
|-------|---|
| Don't know where to start | REVERSE_SYNC_SUMMARY.md |
| Need quick setup | REVERSE_SYNC_QUICK.txt |
| SSH not working | REVERSE_SYNC_SETUP.md → Troubleshooting → SSH Connection Fails |
| Database not syncing | REVERSE_SYNC_SETUP.md → Troubleshooting → Database Sync Fails |
| Flask not restarting | REVERSE_SYNC_SETUP.md → Troubleshooting → Flask Restart Fails |
| Want to understand system | REVERSE_SYNC_ARCHITECTURE.txt |
| Need all details | REVERSE_SYNC_SETUP.md (comprehensive) |

---

## File Size Reference

| File | Size | Time to Read |
|------|------|---|
| REVERSE_SYNC_SUMMARY.md | 6.7 KB | 5 minutes |
| REVERSE_SYNC_QUICK.txt | 2.8 KB | 2 minutes |
| REVERSE_SYNC_SETUP.md | 8.1 KB | 15 minutes |
| REVERSE_SYNC_ARCHITECTURE.txt | 10.3 KB | 10 minutes |
| sync_production_to_local_reverse.sh | 4.4 KB | Review before deploy |

**Total Documentation: ~32 KB**
**Recommended Reading Time: ~35 minutes for complete understanding**

---

## Next Steps

1. ✅ Read **REVERSE_SYNC_SUMMARY.md** (you should do this now)
2. ✅ Read **REVERSE_SYNC_QUICK.txt** (quick overview of steps)
3. ✅ Follow **REVERSE_SYNC_QUICK.txt** (execute all 8 steps)
4. ✅ Test manually on DreamHost (verify it works)
5. ✅ Add to DreamHost crontab (schedule daily sync)
6. ✅ Verify first cron execution (check logs after 3 AM UTC)

---

## Document Version

- **Created**: November 2024
- **Version**: 1.0 (Reverse Sync System)
- **Status**: Ready for production deployment
- **Files Included**: 5 total (4 docs + 1 script)

---

## Quick Start

Already know what to do? Jump to **REVERSE_SYNC_QUICK.txt** and follow the 8 steps.

First time? Start with **REVERSE_SYNC_SUMMARY.md** for a 5-minute overview.

Need deep dive? Read **REVERSE_SYNC_SETUP.md** for comprehensive documentation.

---

**Your recipes sync system is ready to deploy!** 🚀

All files are in: `C:\Users\miket\Recipes_remote\`
