@echo off
setlocal
set "REPORTS_WAGENT_ROOT=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = ($env:REPORTS_WAGENT_ROOT).TrimEnd('\');" ^
  "$statusPath = Join-Path $root '.agent_runtime\status.json';" ^
  "if (-not (Test-Path $statusPath)) { Write-Host 'No agent status file found.'; exit 0 }" ^
  "try { $status = Get-Content $statusPath | ConvertFrom-Json } catch { Write-Host 'Could not read status file.'; exit 1 }" ^
  "if (-not $status.pid) { Write-Host 'No PID found in status file.'; exit 0 }" ^
  "$process = Get-Process -Id $status.pid -ErrorAction SilentlyContinue;" ^
  "if ($process) { Stop-Process -Id $status.pid; Write-Host ('Stopped agent PID ' + $status.pid) } else { Write-Host ('Agent PID ' + $status.pid + ' is not running.') }"

endlocal
