# Sync Quick Reference

## One-Liner Commands

### Test Sync Manually
```bash
ssh ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"
```

### View Sync Log (Last 20 Lines)
```bash
ssh ethel@192.168.2.10 "tail -20 ~/recipes_remote/sync.log"
```

### Watch Sync Log (Real-Time)
```bash
ssh ethel@192.168.2.10 "tail -f ~/recipes_remote/sync.log"
```

### List Backups
```bash
ssh ethel@192.168.2.10 "ls -lh ~/recipes_remote/sync_backups/"
```

### Check Recipe Count on Local Server
```bash
ssh ethel@192.168.2.10 "sqlite3 ~/recipes_remote/recipes.db 'SELECT COUNT(*) FROM recipes WHERE is_valid = 1;'"
```

### Check Recipe Count on Production
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "sqlite3 /home/f42widec/recipes_remote/recipes.db 'SELECT COUNT(*) FROM recipes WHERE is_valid = 1;'"
```

### Restore Latest Backup
```bash
ssh ethel@192.168.2.10 "BACKUP=\$(ls -1t ~/recipes_remote/sync_backups/recipes.db.backup_* | head -1) && cp \$BACKUP ~/recipes_remote/recipes.db && echo 'Restored: '\$BACKUP"
```

### Setup Daily Sync (3 AM)
```bash
ssh ethel@192.168.2.10 "echo '0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh' | crontab -"
```

### View Scheduled Cron Jobs
```bash
ssh ethel@192.168.2.10 "crontab -l"
```

### Remove Sync from Crontab
```bash
ssh ethel@192.168.2.10 "crontab -e"
# Then delete the sync line
```

### Search Sync Log for Errors
```bash
ssh ethel@192.168.2.10 "grep -i error ~/recipes_remote/sync.log"
```

### Get Last Sync Time
```bash
ssh ethel@192.168.2.10 "tail -1 ~/recipes_remote/sync.log"
```

---

## Sync Workflow

```
1. Test manually first:
   ssh ethel@192.168.2.10 "/home/ethel/recipes_remote/sync_production_to_local.sh"

2. Check if it worked:
   ssh ethel@192.168.2.10 "tail -50 ~/recipes_remote/sync.log"

3. If successful, schedule daily:
   ssh ethel@192.168.2.10 "echo '0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh' | crontab -"

4. Verify cron is scheduled:
   ssh ethel@192.168.2.10 "crontab -l"

5. Monitor future syncs:
   ssh ethel@192.168.2.10 "tail -f ~/recipes_remote/sync.log"
```

---

## Troubleshooting

### SSH Key Setup (Passwordless Access)

```bash
# Generate SSH key (Windows)
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\dreamhost_recipes

# Copy to DreamHost
type $env:USERPROFILE\.ssh\dreamhost_recipes.pub | ssh f42widec@pdx1-shared-a3-07.dreamhost.com "cat >> ~/.ssh/authorized_keys"

# Test connection
ssh -i $env:USERPROFILE\.ssh\dreamhost_recipes f42widec@pdx1-shared-a3-07.dreamhost.com "echo OK"
```

### Verify Connectivity

```bash
# Test DreamHost connection
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "test -f /home/f42widec/recipes_remote/recipes.db && echo OK"

# Test Local connection
ssh ethel@192.168.2.10 "test -f ~/recipes_remote/recipes.db && echo OK"
```

### Disk Space Check

```bash
# Local server
ssh ethel@192.168.2.10 "df -h /home/ethel/"

# Production server
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "df -h"
```

---

## Crontab Examples

| Schedule | Crontab Entry |
|----------|---------------|
| Daily 3 AM | `0 3 * * * /home/ethel/recipes_remote/sync_production_to_local.sh` |
| Daily 6 AM | `0 6 * * * /home/ethel/recipes_remote/sync_production_to_local.sh` |
| Every 12 hours | `0 */12 * * * /home/ethel/recipes_remote/sync_production_to_local.sh` |
| Every 6 hours | `0 */6 * * * /home/ethel/recipes_remote/sync_production_to_local.sh` |
| Weekly Monday 3 AM | `0 3 * * 1 /home/ethel/recipes_remote/sync_production_to_local.sh` |

---

## Files

| File | Purpose |
|------|---------|
| `sync_production_to_local.sh` | Main sync script |
| `sync.log` | Sync operation log (local server) |
| `sync_backups/` | Timestamped backup directory (local server) |

---

## Data Flow

```
Production (DreamHost)           Local Server (192.168.2.10)
├── recipes.db          ━━━━━▶   recipes.db
├── saved_recipes_json/ ━━━━━▶   saved_recipes_json/
└── (unchanged)                  ← backups ← (timestamped)
```

Only flows one direction: Production → Local

---

## Key Points

✅ **One-way sync:** Production is master, local is replica
✅ **Automatic backups:** Every sync creates timestamped backup
✅ **Flask restart:** Automatic on local server after sync
✅ **Safe:** Original data backed up before replacement
✅ **Logged:** All operations logged to sync.log
✅ **Restoreable:** Can restore any previous backup anytime

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Password required" | Set up SSH keys (see SSH Key Setup above) |
| Sync takes too long | First run is slower; subsequent runs are faster |
| "Connection timeout" | Check network connectivity with `ping` or `ssh` test |
| Disk full | Clean up old backups: `rm ~/recipes_remote/sync_backups/*old*` |
| Flask won't restart | Manual restart: `cd ~/recipes_remote && ./start.sh` |

---

## Restore From Backup

```bash
# List available backups with their dates
ssh ethel@192.168.2.10 "ls -lhtr ~/recipes_remote/sync_backups/ | tail -10"

# Restore specific backup (replace TIMESTAMP)
TIMESTAMP="20261113_030000"
ssh ethel@192.168.2.10 "cp ~/recipes_remote/sync_backups/recipes.db.backup_$TIMESTAMP ~/recipes_remote/recipes.db"

# Restart Flask
ssh ethel@192.168.2.10 "cd ~/recipes_remote && pkill -f gunicorn; sleep 2; nohup ./start.sh > gunicorn.log 2>&1 &"
```

---

**For complete details, see:** [SYNC_SETUP.md](SYNC_SETUP.md)
