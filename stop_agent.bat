@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0agent_control.ps1" stop
if errorlevel 1 pause
endlocal
