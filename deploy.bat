@echo off
REM DreamHost Deployment Script for Recipes
REM Run this from PowerShell or Command Prompt
REM Usage: deploy.bat

setlocal enabledelayedexpansion

set SSH_USER=f42widec
set SSH_HOST=pdx1-shared-a3-07.dreamhost.com
set LOCAL_PATH=c:\Users\miket\Recipes_remote

echo.
echo ========================================
echo DreamHost Recipes Deployment
echo ========================================
echo.

echo [1/5] Verifying local files...
if not exist "%LOCAL_PATH%\app.py" (
    echo ERROR: app.py not found
    exit /b 1
)
if not exist "%LOCAL_PATH%\recipes.db" (
    echo ERROR: recipes.db not found
    exit /b 1
)
echo  OK: All files found
echo.

echo [2/5] Creating remote directory...
ssh %SSH_USER%@%SSH_HOST% "mkdir -p ~/recipes_remote"
echo  OK: Remote directory created
echo.

echo [3/5] Copying files...
echo  Copying app files...
scp "%LOCAL_PATH%\app.py" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp "%LOCAL_PATH%\recipes.db" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp "%LOCAL_PATH%\requirements.txt" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp "%LOCAL_PATH%\filtered_tags.py" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp "%LOCAL_PATH%\dreamhost_deploy.sh" %SSH_USER%@%SSH_HOST%:~/recipes_remote/

echo  Copying directories...
scp -r "%LOCAL_PATH%\templates" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp -r "%LOCAL_PATH%\static" %SSH_USER%@%SSH_HOST%:~/recipes_remote/
scp -r "%LOCAL_PATH%\saved_recipes_json" %SSH_USER%@%SSH_HOST%:~/recipes_remote/

echo  OK: Files copied
echo.

echo [4/5] Running deployment script on DreamHost...
ssh %SSH_USER%@%SSH_HOST% "cd ~/recipes_remote && bash dreamhost_deploy.sh"
echo  OK: Deployment script complete
echo.

echo [5/5] Starting Flask app...
ssh %SSH_USER%@%SSH_HOST% "cd ~/recipes_remote && nohup ./start.sh > gunicorn.log 2^>^&1 ^& echo $! > gunicorn.pid"
echo  OK: App started
echo.

echo ========================================
echo DEPLOYMENT COMPLETE!
echo ========================================
echo.
echo NEXT STEP:
echo.
echo Contact DreamHost admin and ask them to add this nginx config:
echo.
echo location /food55/ {
echo     rewrite ^/food55/(.*)$ /$1 break;
echo     proxy_pass http://127.0.0.1:8055;
echo     proxy_set_header Host $host;
echo     proxy_set_header X-Real-IP $remote_addr;
echo     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
echo     proxy_set_header X-Forwarded-Proto $scheme;
echo }
echo.
echo location /food55/static/ {
echo     alias /home/f42widec/recipes_remote/static/;
echo     expires 30d;
echo }
echo.
echo After admin confirms, test: http://www.42wide.com/food55/
echo.
pause
