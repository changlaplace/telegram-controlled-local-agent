@echo off
setlocal
call "%~dp0stop_agent.bat"
timeout /t 2 /nobreak >nul
call "%~dp0start_agent.bat"
endlocal
