@echo off
setlocal
set "REPORTS_WAGENT_ROOT=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = ($env:REPORTS_WAGENT_ROOT).TrimEnd('\');" ^
  "$runtime = Join-Path $root '.agent_runtime';" ^
  "$statusPath = Join-Path $runtime 'status.json';" ^
  "New-Item -ItemType Directory -Force $runtime | Out-Null;" ^
  "$alreadyRunning = $false;" ^
  "if (Test-Path $statusPath) {" ^
  "  try {" ^
  "    $status = Get-Content $statusPath | ConvertFrom-Json;" ^
  "    if ($status.pid -and (Get-Process -Id $status.pid -ErrorAction SilentlyContinue)) { $alreadyRunning = $true }" ^
  "  } catch {}" ^
  "}" ^
  "if (-not $alreadyRunning) {" ^
  "  Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -ArgumentList 'main.py' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'agent.out.log') -RedirectStandardError (Join-Path $runtime 'agent.err.log');" ^
  "}" ^
  "Start-Process -FilePath (Join-Path $root '.venv\Scripts\pythonw.exe') -ArgumentList 'monitor.py' -WorkingDirectory $root;"

endlocal
