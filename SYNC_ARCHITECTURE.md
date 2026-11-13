# Sync Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Your Windows Machine (Development)                             │
│  └─ Runs: Cron job scheduler / Monitoring                       │
│  └─ Triggers sync daily at 3 AM UTC                             │
│                                                                 │
└────────────────────┬──────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         │ (SSH connection)      │
         │                       │
         ▼                       ▼
    
┌─────────────────────┐     ┌──────────────────────────┐
│  Production Server  │     │   Local Server           │
│  (DreamHost)        │     │   (192.168.2.10)         │
│                     │     │                          │
│ f42widec@pdx1...    │     │ ethel@192.168.2.10       │
│ /home/f42widec/     │     │ /home/ethel/             │
│ recipes_remote/     │     │ recipes_remote/          │
│                     │     │                          │
│ ✓ recipes.db        │────▶│ ✓ recipes.db (copied)   │
│ ✓ saved_recipes_    │────▶│ ✓ saved_recipes_json/   │
│   json/             │     │   (copied)               │
│ ✓ app.py            │     │ ✓ app.py (separate)      │
│ ✓ Flask running     │     │ ✓ Flask running          │
│ ✓ 809 recipes       │     │ ✓ 809 recipes (updated)  │
│                     │     │                          │
│ (MASTER)            │     │ (REPLICA)                │
│ (Read-write)        │     │ (Read-only via sync)     │
└─────────────────────┘     └────────┬─────────────────┘
        ▲                            │
        │                            │
        │ (Production URL)           │ (Local URL)
        │                            │
        ▼                            ▼
   www.42wide.com/food55      http://192.168.2.10:5000
   (Public)                   (Private/Local)
```

---

## Daily Sync Process

```
┌─────────────────────────────────────────────────────────────────┐
│ DAILY SYNC PROCESS (Every 3 AM UTC)                             │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────┐
    │ 3:00 AM - Cron Job Triggered on Local Server         │
    │ $ /home/ethel/recipes_remote/sync_production_to_     │
    │   local.sh                                           │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 1: Connectivity Check                           │
    │ ✓ Can reach production (f42widec@pdx1...)           │
    │ ✓ Can reach local (ethel@192.168.2.10)              │
    │ ✓ recipes.db exists on both servers                 │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 2: Prepare Files                                │
    │ Production:                                          │
    │  cp recipes.db → /tmp/recipes.db.sync_PID            │
    │  chmod 644 (make readable)                           │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 3: Download from Production                     │
    │ scp f42widec@pdx1:.../recipes.db.sync_PID           │
    │     → /tmp/recipes.db.from_prod_PID                 │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 4: Backup Current Local Database                │
    │ scp ethel@192.168.2.10:.../recipes.db               │
    │     → ~/sync_backups/recipes.db.backup_TIMESTAMP    │
    │                                                      │
    │ Example: recipes.db.backup_20261113_030000          │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 5: Upload New Database                          │
    │ scp /tmp/recipes.db.from_prod_PID                   │
    │     → ethel@192.168.2.10:.../recipes.db             │
    │                                                      │
    │ Local server now has production database             │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 6: Sync JSON Directory                          │
    │ rsync (or scp fallback)                              │
    │ f42widec@pdx1:.../saved_recipes_json/               │
    │ → ethel@192.168.2.10:.../saved_recipes_json/        │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 7: Restart Flask on Local Server                │
    │ pkill -f gunicorn                                    │
    │ sleep 2                                              │
    │ nohup ./start.sh > gunicorn.log 2>&1 &              │
    │                                                      │
    │ Flask now uses new production database               │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ STEP 8: Cleanup & Log                                │
    │ rm /tmp/recipes.db.from_prod_PID                    │
    │ rm /tmp/recipes.db.sync_PID (on production)         │
    │                                                      │
    │ Log entry added to sync.log:                         │
    │ [2026-11-13 03:00:45] SUCCESS: Sync completed!     │
    │ [2026-11-13 03:00:45] Backup saved to:              │
    │ ~/sync_backups/recipes.db.backup_20261113_030045   │
    └──────────────┬───────────────────────────────────────┘
                   │
    ┌──────────────▼───────────────────────────────────────┐
    │ 3:01 AM - Sync Complete ✓                            │
    │                                                      │
    │ Local server now has:                                │
    │ • Latest recipes from production                     │
    │ • Up-to-date saved_recipes_json/                     │
    │ • Flask running with new data                        │
    │ • Previous version backed up                         │
    └──────────────────────────────────────────────────────┘
```

---

## File Transfer Flow

```
┌─────────────────────────────────────────────────────────────┐
│ PRODUCTION SERVER                   LOCAL SERVER            │
│ (DreamHost)                         (192.168.2.10)          │
└─────────────────────────────────────────────────────────────┘

Before Sync:
  recipes.db (v1)                recipes.db (v0)
  size: 4.2 MB                   size: 4.1 MB
  recipes: 809                   recipes: 808
  modified: today 12:00 AM       modified: yesterday

Download via SCP:
  recipes.db (v1) 
        │
        ├─── Copy to /tmp ──────────┐
        │                           │
        ├─────── Download ──────────┼──── /tmp/recipes.db.from_prod
        │                           │
        └─────── Local Backup ──────┴──── sync_backups/
                                         recipes.db.backup_
                                         20261113_030000

After Sync:
  recipes.db (v1)                recipes.db (v1) ← NEW
  size: 4.2 MB                   size: 4.2 MB
  recipes: 809                   recipes: 809
  modified: today 12:00 AM       modified: today 03:00 AM
  
                                 Backup: recipes.db.backup_
                                        20261113_030000 ← OLD
```

---

## Backup Timeline

```
Sync Backup History (Example):

sync_backups/
├── recipes.db.backup_20261106_030000  (7 days old)
├── recipes.db.backup_20261107_030000  (6 days old)
├── recipes.db.backup_20261108_030000  (5 days old)
├── recipes.db.backup_20261109_030000  (4 days old)
├── recipes.db.backup_20261110_030000  (3 days old)
├── recipes.db.backup_20261111_030000  (2 days old)
├── recipes.db.backup_20261112_030000  (1 day old)
└── recipes.db.backup_20261113_030000  (TODAY - most recent)

Can restore to any point in time!

Example: Restore from 3 days ago
  $ cp sync_backups/recipes.db.backup_20261110_030000 recipes.db
  $ restart_flask
```

---

## Error Handling Flow

```
Start Sync
    │
    ├─ Cannot reach production?
    │  └─ ERROR: Exit with status 1
    │     └─ Log error
    │     └─ Don't touch local database
    │
    ├─ Cannot reach local?
    │  └─ ERROR: Exit with status 1
    │     └─ Log error
    │     └─ Don't change anything
    │
    ├─ Download fails?
    │  └─ ERROR: Exit with status 1
    │     └─ Log error
    │     └─ Clean up temp files
    │     └─ Local database unchanged
    │
    ├─ Backup fails?
    │  └─ ERROR: Exit with status 1
    │     └─ Log error
    │     └─ Clean up temp files
    │     └─ Local database unchanged
    │
    ├─ Upload fails?
    │  └─ ERROR: Exit with status 1
    │     └─ Log error
    │     └─ Restore from backup
    │     └─ Local database unchanged
    │
    └─ All successful?
       └─ SUCCESS: Exit with status 0
          └─ Log success
          └─ Backup created
          └─ Flask restarted
          └─ Sync complete
```

---

## Network Diagram

```
        Your Windows Machine
              │
              │ SSH
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
DreamHost           Local Network
(Public)            (Private - 192.168.x.x)
    │                   │
    │                   ▼
    │            ethel@192.168.2.10
    │            (Local Server)
    │                   │
    ▼                   ▼
f42widec@pdx1...   /home/ethel/
/home/f42widec/    recipes_remote/
recipes_remote/         │
    │                   ▼
    ├─ recipes.db      Flask (5000)
    ├─ app.py          (Local app)
    ├─ Flask           │
    └─ (Public app)    ▼
         │         http://192.168.2.10:5000
         │         (Access via local network)
         │
         ▼
  www.42wide.com/food55
  (Public access)
```

---

## Sync States

```
STATE 1: BEFORE SYNC
┌─────────────────────┐  ┌─────────────────────┐
│  Production         │  │  Local              │
│                     │  │                     │
│  recipes: 809       │  │  recipes: 808       │
│  last update:       │  │  last update:       │
│  today 2:00 PM      │  │  yesterday 3:00 AM  │
│                     │  │                     │
│  → Recipes added    │  │  → Out of date      │
│    on production    │  │    recipes on local │
└─────────────────────┘  └─────────────────────┘
         │                      │
         │   Sync starts        │
         └──────────┬───────────┘
                    │

STATE 2: DURING SYNC
                ┌──────────────┐
                │ Downloading  │
                │ 4.2 MB       │
                │ ...          │
                └──────────────┘
                      │
                      │ 50% complete
                      │
                ┌──────────────┐
                │ Uploading    │
                │ 4.2 MB       │
                │ ...          │
                └──────────────┘

STATE 3: AFTER SYNC
┌─────────────────────┐  ┌─────────────────────┐
│  Production         │  │  Local              │
│                     │  │                     │
│  recipes: 809       │  │  recipes: 809 ✓     │
│  last update:       │  │  last update:       │
│  today 2:00 PM      │  │  today 3:00 AM ✓    │
│                     │  │                     │
│  (unchanged)        │  │  → Up to date!      │
│  (master copy)      │  │  (replica copy)     │
└─────────────────────┘  └─────────────────────┘
         │                      │
         │                      │
         │                   Backup created:
         │                recipes.db.backup_
         │                20261113_030000
```

---

## Rollback Process

```
Need to undo a sync? (e.g., corrupted data, wrong recipes)

Step 1: Identify backup to restore
$ ssh ethel@192.168.2.10 "ls -1 ~/recipes_remote/sync_backups/"
  recipes.db.backup_20261112_030000  ← Select this one
  recipes.db.backup_20261111_030000
  recipes.db.backup_20261110_030000

Step 2: Restore from backup
$ ssh ethel@192.168.2.10 \
  "cp ~/recipes_remote/sync_backups/recipes.db.backup_20261112_030000 \
       ~/recipes_remote/recipes.db"

Step 3: Restart Flask
$ ssh ethel@192.168.2.10 \
  "cd ~/recipes_remote && pkill -f gunicorn; sleep 2; \
   nohup ./start.sh > gunicorn.log 2>&1 &"

Step 4: Verify
$ ssh ethel@192.168.2.10 \
  "sqlite3 ~/recipes_remote/recipes.db 'SELECT COUNT(*) FROM recipes;'"
  → Should show recipe count from that backup

DONE! Local server is back to previous state.
```

---

This architecture ensures:

✅ **One-way flow** (production → local only)
✅ **No corruption** (backups before changes)
✅ **Easy rollback** (can restore any backup)
✅ **Automatic process** (runs on schedule)
✅ **Safe failure** (stops if connectivity issue)
