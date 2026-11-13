# SSH Reverse Tunnel Deployment Status

## ✅ TUNNEL SUCCESSFULLY DEPLOYED AND ACTIVE

### Current Status
- **Tunnel Process:** Active (PID: 27158)
- **Tunnel Command:** `ssh -i /home/ethel/.ssh/id_rsa -R 2222:localhost:22 -N -f`
- **Local Server:** ethel@192.168.2.10
- **DreamHost Server:** f42widec@pdx1-shared-a3-07.dreamhost.com
- **Tunnel Port:** 2222 (on DreamHost)

### What Was Fixed
1. **Line Ending Issue:** Converted CRLF (Windows) to LF (Unix) line endings
2. **SSH Key:** Updated script to use existing `~/.ssh/id_rsa` (which is already authorized on DreamHost)
3. **Script Permissions:** Made `start_reverse_tunnel.sh` executable
4. **SSH Config:** Updated local SSH config to prefer key-based authentication

### Tunnel Logs (Recent)
```
[2026-11-13 14:38:56] Starting SSH reverse tunnel to DreamHost...
[2026-11-13 14:38:58] ✓ Tunnel started successfully (PID: 27158)
[2026-11-13 14:39:04] Status check: Tunnel is active
```

## 🚀 NEXT STEPS

### 1. Verify Tunnel from DreamHost Console (Manual)

SSH into DreamHost directly and run:
```bash
ssh -p 2222 ethel@localhost "hostname"
```

This should return the hostname of your local server (ethel@hp1 or similar).

### 2. Set Up Cron for Tunnel Healthcheck (Local Server)

On your local server, add this to crontab:
```bash
crontab -e
```

Add this line:
```
*/5 * * * * /home/ethel/recipes_remote/start_reverse_tunnel.sh check >/dev/null 2>&1
```

This checks every 5 minutes if the tunnel is alive and restarts it if needed.

### 3. Deploy Sync Script to DreamHost

Copy the sync script to DreamHost:
```bash
scp C:\Users\miket\Recipes_remote\sync_via_tunnel.sh f42widec@pdx1-shared-a3-07.dreamhost.com:~/recipes_remote/
```

Fix line endings on DreamHost:
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "sed -i 's/\r$//' ~/recipes_remote/sync_via_tunnel.sh && chmod +x ~/recipes_remote/sync_via_tunnel.sh"
```

### 4. Test Sync Manually (From DreamHost)

SSH into DreamHost and run:
```bash
~/recipes_remote/sync_via_tunnel.sh
```

This should:
- Connect through tunnel to local server
- Back up recipes
- Copy files
- Restart Flask
- Log results

### 5. Add Sync Cron to DreamHost

SSH into DreamHost and add to crontab:
```bash
crontab -e
```

Add this line (runs daily at 3 AM UTC):
```
0 3 * * * ~/recipes_remote/sync_via_tunnel.sh >> ~/recipes_remote/sync.log 2>&1
```

## 🔍 Troubleshooting

### If Tunnel Not Active
Run on local server:
```bash
~/recipes_remote/start_reverse_tunnel.sh restart
~/recipes_remote/start_reverse_tunnel.sh status
```

### If You Get "Cannot Execute" Error
Fix line endings:
```bash
sed -i 's/\r$//' ~/recipes_remote/start_reverse_tunnel.sh
chmod +x ~/recipes_remote/start_reverse_tunnel.sh
```

### If SSH Connection to DreamHost Fails
Check SSH config:
```bash
cat ~/.ssh/config
```

Should show:
```
Host pdx1-shared-a3-07.dreamhost.com
    PubkeyAuthentication yes
    IdentityFile ~/.ssh/id_rsa
```

### If Sync Doesn't Run
Check logs on DreamHost:
```bash
tail -50 ~/recipes_remote/sync.log
```

Or manually test sync:
```bash
~/recipes_remote/sync_via_tunnel.sh
```

## 📋 Verification Checklist

- [x] Tunnel script has Unix line endings
- [x] Tunnel script is executable
- [x] SSH key is authorized on DreamHost
- [x] SSH config is set up correctly
- [x] Tunnel is actively running
- [ ] Can connect through tunnel from DreamHost
- [ ] Sync script deployed to DreamHost
- [ ] Sync script has Unix line endings
- [ ] Sync script is executable
- [ ] Tunnel healthcheck in local crontab
- [ ] Sync job in DreamHost crontab
- [ ] First sync completes successfully

## 📁 Files

### Local Server (192.168.2.10)
- `/home/ethel/recipes_remote/start_reverse_tunnel.sh` - Tunnel manager
- `/home/ethel/recipes_remote/tunnel.log` - Tunnel logs
- `/home/ethel/.ssh/id_rsa` - SSH private key

### DreamHost
- `~/recipes_remote/sync_via_tunnel.sh` - Sync script (to be deployed)
- `~/recipes_remote/sync.log` - Sync logs (created after first run)

## 🎯 Architecture Reminder

```
Local Server (192.168.2.10)
├─ Runs: ssh -R 2222:localhost:22 f42widec@pdx1-shared-a3-07.dreamhost.com
└─ Creates: Persistent tunnel listening on DreamHost port 2222

Every 5 minutes:
├─ Cron runs: start_reverse_tunnel.sh check
└─ Verifies tunnel is alive, restarts if needed

Every day at 3 AM UTC:
├─ DreamHost cron runs: sync_via_tunnel.sh
├─ Connects: ssh -p 2222 ethel@localhost (through tunnel)
├─ Copies: Recipes via SCP (through tunnel)
├─ Restarts: Flask on local server
└─ Logs: Everything to ~/recipes_remote/sync.log
```

## ✅ Status Summary

**TUNNEL:** ✓ Active and working
**SSH AUTH:** ✓ Using existing authorized key
**NEXT:** Deploy sync script and add cron jobs
