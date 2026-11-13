# SSH Reverse Tunnel - Debugging Guide

## If Manual Sync Fails

### Step 1: Test Tunnel Connectivity
On DreamHost, run:
```bash
# Check if port 2222 is listening
ss -tln | grep 2222

# Expected output (should show LISTEN):
# LISTEN 0 128 127.0.0.1:2222
```

### Step 2: Test SSH Connection Through Tunnel
On DreamHost, run with verbose output:
```bash
ssh -vvv -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 ethel@localhost "whoami" 2>&1
```

**Expected output:**
```
debug1: Connection established
debug1: Remote protocol version...
...
ethel
```

**If you see "Permission denied":**
- The tunnel connection works, but SSH authentication failed
- The DreamHost public key may not be in local authorized_keys
- Solution: Run on local server: `cat ~/.ssh/authorized_keys | grep f42widec`

**If you see "Connection refused":**
- The tunnel port 2222 is not listening
- The tunnel may have crashed
- Solution: On local server, run: `~/recipes_remote/start_reverse_tunnel.sh restart`

### Step 3: Verify Local SSH Server
On local server, run:
```bash
# Check SSH server is running
systemctl status ssh
# OR
ps aux | grep sshd

# Check it's listening on port 22
ss -tln | grep :22
```

### Step 4: Check SSH Keys
On local server:
```bash
# List authorized keys
cat ~/.ssh/authorized_keys

# Should include both:
# 1. Your personal key (miket-to-hp1)
# 2. DreamHost key (f42widec@pdx1-shared-a3-07)
```

On DreamHost:
```bash
# Check private key exists
ls -la ~/.ssh/id_rsa

# Check SSH permissions
ls -la ~/.ssh/
# Should be: drwx------ (700)
```

### Step 5: Test Each Component

**Test 1: Local to DreamHost SSH (no tunnel)**
```bash
# On local server
ssh f42widec@pdx1-shared-a3-07.dreamhost.com "echo OK"
# Should print: OK
```

**Test 2: Tunnel creation**
```bash
# On local server
~/recipes_remote/start_reverse_tunnel.sh restart
~/recipes_remote/start_reverse_tunnel.sh status
# Should print: ✓ Tunnel is active
```

**Test 3: Port forwarding**
```bash
# On DreamHost
ss -tln | grep 2222
# Should show listening on 127.0.0.1:2222
```

**Test 4: SSH through tunnel**
```bash
# On DreamHost
ssh -p 2222 ethel@localhost "echo OK"
# Should print: OK
```

**Test 5: SCP through tunnel**
```bash
# On DreamHost - copy a small test file
scp -P 2222 /home/f42widec/test.txt ethel@localhost:/home/ethel/
# Should complete without errors
```

## Common Issues and Fixes

### Issue: "Cannot connect to local server via tunnel"
**Cause:** Port 2222 is not listening on DreamHost

**Check:**
```bash
# On DreamHost
ss -tln | grep 2222
# Should show LISTEN - if not, tunnel crashed
```

**Fix:**
```bash
# On local server
~/recipes_remote/start_reverse_tunnel.sh restart
```

---

### Issue: "ethel@localhost's password:"
**Cause:** SSH key authentication failed

**Check:**
```bash
# On DreamHost - list keys being tried
ssh -vv -p 2222 ethel@localhost "whoami" 2>&1 | grep -E "(Trying|Offering|Permission)"
```

**Fix:**
```bash
# On local server - verify DreamHost's public key is authorized
cat ~/.ssh/authorized_keys | grep f42widec
# Should show: ssh-rsa AAAAB3NzaC1y...f42widec@pdx1-shared-a3-07

# If not present, add it:
echo "ssh-rsa AAAAB3NzaC1y...f42widec@pdx1-shared-a3-07" >> ~/.ssh/authorized_keys
```

---

### Issue: Tunnel dies/restarts frequently
**Cause:** Network issues or SSH server problems

**Check logs:**
```bash
# On local server
cat ~/recipes_remote/tunnel.log | tail -20
```

**Solutions:**
1. Restart tunnel:
   ```bash
   ~/recipes_remote/start_reverse_tunnel.sh restart
   ```

2. Check SSH connectivity:
   ```bash
   ssh -o ConnectTimeout=10 f42widec@pdx1-shared-a3-07.dreamhost.com "echo OK"
   ```

3. Verify network:
   ```bash
   ping -c 3 pdx1-shared-a3-07.dreamhost.com
   ```

---

### Issue: Sync script hangs
**Cause:** Usually SSH timeouts or stalled processes

**Kill hung process:**
```bash
# On DreamHost - find and kill hanging sync
ps aux | grep sync_via_tunnel.sh
kill -9 <PID>
```

**Restart with timeout:**
```bash
# Try with explicit timeout
timeout 120 ~/recipes_remote/sync_via_tunnel.sh
```

---

### Issue: "Connection refused" when testing tunnel
**Cause:** Tunnel process crashed or didn't start

**Debug:**
```bash
# On local server - check process
ps aux | grep "ssh.*-R.*2222" | grep -v grep

# Check logs
tail -20 ~/recipes_remote/tunnel.log

# Restart tunnel
~/recipes_remote/start_reverse_tunnel.sh stop
sleep 2
~/recipes_remote/start_reverse_tunnel.sh start
sleep 2
~/recipes_remote/start_reverse_tunnel.sh status
```

## Advanced Debugging

### Enable SSH Debug Output
For detailed SSH debugging on local:
```bash
# Check tunnel connection quality
ssh -vvv -R 2222:localhost:22 -N f42widec@pdx1-shared-a3-07.dreamhost.com
# Watch for: "Allocated local forwarding for..."
# This confirms port forwarding is working
```

### Monitor Tunnel in Real-time
```bash
# On local server - watch tunnel
watch -n 1 'ps aux | grep "ssh.*-R.*2222" | grep -v grep; ss -tln | grep 2222'
```

### Check SSH Server Logs
```bash
# On local server - if SSH has logging enabled
tail -20 /var/log/auth.log
tail -20 /var/log/syslog
```

### Verify SSH Key Permissions
Incorrect permissions can cause key auth to fail:
```bash
# On local server
ls -la ~/.ssh/
# Should be: drwx------ (700)

ls -la ~/.ssh/authorized_keys
# Should be: -rw------- (600)

# On DreamHost
ls -la ~/.ssh/
# Should be: drwx------ (700)

ls -la ~/.ssh/id_rsa
# Should be: -rw------- (600)
```

Fix permissions if needed:
```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/id_rsa
```

## Testing Sync Script Components

### Test 1: Database Sync
```bash
# On DreamHost
ssh -p 2222 ethel@localhost "test -f /home/ethel/recipes_remote/recipes.db && echo 'Database exists' || echo 'Database missing'"
```

### Test 2: Create Backup
```bash
# On DreamHost
ssh -p 2222 ethel@localhost "mkdir -p /home/ethel/recipes_remote/sync_backups && echo 'Backup dir ready'"
```

### Test 3: Copy File via SCP
```bash
# On DreamHost - copy production DB to local via tunnel
scp -P 2222 /home/f42widec/recipes_remote/recipes.db ethel@localhost:/home/ethel/recipes_remote/recipes.db.test
```

### Test 4: Run Single Sync Step
```bash
# On local server - list what would be synced
ssh -p 2222 ethel@localhost "ls -la /home/ethel/recipes_remote/ | head -20"
```

## Quick Health Check

Run this to verify everything is set up correctly:
```bash
#!/bin/bash
echo "1. Checking tunnel..."
ps aux | grep "ssh.*-R.*2222" | grep -v grep && echo "✓ Tunnel running" || echo "✗ Tunnel stopped"

echo "2. Checking port 2222..."
ss -tln | grep 2222 > /dev/null && echo "✓ Port listening" || echo "✗ Port not listening"

echo "3. Checking authorized_keys..."
grep f42widec ~/.ssh/authorized_keys > /dev/null && echo "✓ DreamHost key found" || echo "✗ DreamHost key missing"

echo "4. Checking local SSH..."
systemctl status ssh | grep active > /dev/null && echo "✓ SSH server running" || echo "✗ SSH server stopped"

echo "5. Checking sync script..."
test -x ~/recipes_remote/sync_via_tunnel.sh && echo "✓ Sync script executable" || echo "✗ Sync script not executable"
```

Run this weekly to catch issues early!

---

**Last Updated:** 2026-11-13  
**For more help:** See TUNNEL_SETUP_PROGRESS.md
