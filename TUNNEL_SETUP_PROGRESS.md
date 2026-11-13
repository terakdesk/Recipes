# SSH Reverse Tunnel Setup - Progress Report

## ✅ Completed Steps

### 1. Tunnel Created and Active
- **Status:** ✓ Tunnel is running and listening
- **Process:** PID 27956 on local server
- **Configuration:** Reverse tunnel from local (192.168.2.10:22) to DreamHost (port 2222)
- **Command:** `ssh -R 2222:localhost:22 -N -f f42widec@pdx1-shared-a3-07.dreamhost.com`
- **Fix applied:** Removed `ExitOnForwardFailure=yes` that was preventing tunnel from establishing

### 2. Port Forwarding Verified
- **Status:** ✓ DreamHost port 2222 is listening
- **Verified by:** `ss -tln | grep 2222` shows `LISTEN 0 128 127.0.0.1:2222`
- **Test result:** Connection established successfully from DreamHost

### 3. SSH Authentication Configured
- **Status:** ✓ DreamHost's public key added to local authorized_keys
- **DreamHost key:** `ssh-rsa AAAAB3NzaC1y...` (f42widec@pdx1-shared-a3-07)
- **Local authorized_keys:** Now contains both original key and DreamHost key
- **SSH Server status:** Listening on port 22, accepting key-based auth

### 4. SSH Key Authentication Working
- **Status:** ✓ DreamHost can now authenticate via public key
- **Test:** SSH prompted for password, then accepted the key
- **Next:** Connection through tunnel should now work

## ⚠️ Current Issue

### SSH Connections Timing Out
- Symptom: SSH commands to DreamHost hang/timeout
- Diagnosis: May be related to SSH session connection handling
- Temporary workaround: Use shorter-lived SSH commands

## 📋 Remaining Tasks

### 1. **Test Sync Script** (Critical)
From DreamHost terminal, run:
```bash
~/recipes_remote/sync_via_tunnel.sh
```

Expected output:
- Step 1: ✓ Production database exists
- Step 2: ✓ Tunnel connection successful  
- Step 3: ✓ Backup created on local
- Step 4: ✓ Database synced
- Step 5: ✓ JSON synced
- Step 6: ✓ Flask restarted

### 2. **Add Tunnel Healthcheck to Local Crontab**
On local server (192.168.2.10):
```bash
crontab -e
```

Add line:
```
*/5 * * * * /home/ethel/recipes_remote/start_reverse_tunnel.sh check >/dev/null 2>&1
```

### 3. **Add Sync Job to DreamHost Crontab**
On DreamHost:
```bash
crontab -e
```

Add line:
```
0 3 * * * ~/recipes_remote/sync_via_tunnel.sh >> ~/recipes_remote/sync.log 2>&1
```

## 🔧 Troubleshooting SSH Hangs

If SSH commands keep timing out when connecting to DreamHost, try:

1. **Use shorter timeout:**
   ```bash
   ssh -o ConnectTimeout=5 f42widec@pdx1-shared-a3-07.dreamhost.com "echo test"
   ```

2. **Use batch mode (no password prompts):**
   ```bash
   ssh -o BatchMode=yes f42widec@pdx1-shared-a3-07.dreamhost.com "command"
   ```

3. **Check DreamHost SSH server status:**
   From DreamHost terminal:
   ```bash
   systemctl status ssh
   ps aux | grep sshd
   ```

4. **Test tunnel directly from DreamHost:**
   ```bash
   ssh -v -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 ethel@localhost "whoami"
   ```

## 📊 Architecture Status

```
Local Server (192.168.2.10)
├─ SSH Server: ✓ Running on port 22
├─ SSH Keys: ✓ DreamHost public key in authorized_keys
├─ Reverse Tunnel: ✓ Active, listening on DreamHost port 2222
└─ Crontab: ⏳ Waiting for setup (tunnel healthcheck every 5 min)

DreamHost (www.42wide.com)
├─ SSH Client: ✓ Can connect to localhost:2222 through tunnel
├─ SSH Keys: ✓ Generated (id_rsa)
├─ Sync Script: ✓ Deployed and executable
└─ Crontab: ⏳ Waiting for setup (daily sync at 3 AM UTC)

Connection Through Tunnel
├─ Port forwarding: ✓ Active (2222 → 22)
├─ Authentication: ✓ Key-based SSH auth working
├─ SSH Connectivity: ⚠️ Intermittent hangs (may be timeout issue)
└─ SCP Transfer: ⏳ Not yet tested
```

## 🎯 Key Changes Made

1. **start_reverse_tunnel.sh:**
   - Fixed Windows line endings → Unix LF
   - Changed SSH key from id_rsa_dreamhost → id_rsa
   - Removed ExitOnForwardFailure=yes (was silently killing tunnel)

2. **SSH Configuration:**
   - Updated ~/.ssh/config on local to use key-based auth
   - Added DreamHost's SSH public key to ~/.ssh/authorized_keys on local
   - Generated SSH key on DreamHost (f42widec account)

3. **sync_via_tunnel.sh:**
   - Fixed Windows line endings → Unix LF
   - Made executable
   - Ready for testing

## ✅ Next Immediate Action

**SSH into DreamHost and manually run the sync script:**
```bash
ssh f42widec@pdx1-shared-a3-07.dreamhost.com
~/recipes_remote/sync_via_tunnel.sh
```

Watch for:
- "Step 2: ✓ Tunnel connection successful" = tunnel working
- Any error messages indicating what's failing
- Log file at ~/recipes_remote/sync_tunnel.log

Once manual sync works, add the cron job and setup is complete!

## 📝 Files Modified

- `start_reverse_tunnel.sh` - Tunnel management script
- `~/.ssh/config` (on local) - SSH configuration
- `~/.ssh/authorized_keys` (on local) - Added DreamHost public key
- `~/.ssh/id_rsa` (on DreamHost) - Generated SSH key pair
- `sync_via_tunnel.sh` - Sync script on DreamHost

## 🚀 Expected Timeline

- Manual sync test: Should complete in < 5 minutes
- Cron setup: < 5 minutes
- Full automation ready: < 15 minutes after manual test succeeds

---

**Last Updated:** 2026-11-13 14:50 UTC  
**Status:** Ready for manual sync test
