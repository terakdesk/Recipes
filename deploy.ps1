param(
  [string]$TargetHost = 'me@192.168.2.170',
  [string]$RemoteDir = '~/recipes_remote'
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "Copying app.py and templates to ${TargetHost}:$RemoteDir"
scp "$scriptDir\app.py" "${TargetHost}:$RemoteDir/"
scp -r "$scriptDir\templates" "${TargetHost}:$RemoteDir/"

Write-Host "Restarting recipes.service on $TargetHost and showing recent journal lines"
ssh $TargetHost "sudo systemctl restart recipes.service; sudo journalctl -u recipes.service -n 80 --no-pager"

Write-Host "Checking unix socket response (may fail if service not ready)"
ssh $TargetHost "curl -v --unix-socket /run/recipes/recipes.sock http://localhost/ -I" | Write-Host

Write-Host 'Done.'
