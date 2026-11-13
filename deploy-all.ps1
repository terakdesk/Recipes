# DreamHost Complete Deployment - Automated

$SshUser = "f42widec"
$SshHost = "pdx1-shared-a3-07.dreamhost.com"
$LocalAppPath = "c:\Users\miket\Recipes_remote"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DreamHost Complete Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check local files
Write-Host "[1/6] Verifying local files..." -ForegroundColor Green
$requiredFiles = @('app.py', 'recipes.db', 'requirements.txt', 'filtered_tags.py', 'dreamhost_deploy.sh')
foreach ($file in $requiredFiles) {
    if (Test-Path "$LocalAppPath\$file") {
        Write-Host "  OK: $file"
    } else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  OK: templates directory"
Write-Host "  OK: static directory"  
Write-Host "  OK: saved_recipes_json directory"
Write-Host ""

# Create remote dir
Write-Host "[2/6] Creating remote directory..." -ForegroundColor Green
ssh $SshUser@$SshHost "mkdir -p ~/recipes_remote" 2>&1 | Out-Null
Write-Host "  Remote directory ready"
Write-Host ""

# Copy files
Write-Host "[3/6] Copying files to DreamHost..." -ForegroundColor Green
Write-Host "  Copying: app.py, recipes.db, requirements.txt, filtered_tags.py, dreamhost_deploy.sh"
$dest = "$SshUser@$($SshHost)`:~/recipes_remote/"

scp "$LocalAppPath\app.py" $dest 2>&1 | Out-Null
scp "$LocalAppPath\recipes.db" $dest 2>&1 | Out-Null
scp "$LocalAppPath\requirements.txt" $dest 2>&1 | Out-Null
scp "$LocalAppPath\filtered_tags.py" $dest 2>&1 | Out-Null
scp "$LocalAppPath\dreamhost_deploy.sh" $dest 2>&1 | Out-Null

Write-Host "  Files copied"
Write-Host ""

# Copy directories
Write-Host "[4/6] Copying directories (templates, static, recipes)..." -ForegroundColor Green
Write-Host "  This may take a minute..."
scp -r "$LocalAppPath\templates" $dest 2>&1 | Out-Null
scp -r "$LocalAppPath\static" $dest 2>&1 | Out-Null
scp -r "$LocalAppPath\saved_recipes_json" $dest 2>&1 | Out-Null
Write-Host "  Directories copied"
Write-Host ""

# Run deployment
Write-Host "[5/6] Running deployment script on DreamHost..." -ForegroundColor Green
$deployCmd = "cd ~/recipes_remote && bash dreamhost_deploy.sh"
$deployOutput = ssh $SshUser@$SshHost $deployCmd 2>&1

if ($deployOutput -match "DEPLOYMENT COMPLETE") {
    Write-Host "  Deployment successful!"
} else {
    Write-Host $deployOutput
}
Write-Host ""

# Start app
Write-Host "[6/6] Starting Flask application..." -ForegroundColor Green
$startCmd = 'cd ~/recipes_remote && nohup ./start.sh > gunicorn.log 2>&1 & echo $! > gunicorn.pid; sleep 3; ps -p $(cat gunicorn.pid) > /dev/null 2>&1 && echo OK || echo FAIL'
$startResult = ssh $SshUser@$SshHost $startCmd 2>&1

if ($startResult -match "OK") {
    Write-Host "  App started successfully!"
} else {
    Write-Host "  App status: Check via SSH"
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "NEXT STEP:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Contact DreamHost admin with this nginx config:"
Write-Host ""
Write-Host "location /food55/ {"
Write-Host "    rewrite ^/food55/(.*) /$1 break;"
Write-Host "    proxy_pass http://127.0.0.1:8055;"
Write-Host "    proxy_set_header Host `$host;"
Write-Host "    proxy_set_header X-Real-IP `$remote_addr;"
Write-Host "    proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;"
Write-Host "    proxy_set_header X-Forwarded-Proto `$scheme;"
Write-Host "}"
Write-Host ""
Write-Host "location /food55/static/ {"
Write-Host "    alias /home/f42widec/recipes_remote/static/;"
Write-Host "    expires 30d;"
Write-Host "}"
Write-Host ""
Write-Host "After admin confirms, test: http://www.42wide.com/food55/"
Write-Host ""
