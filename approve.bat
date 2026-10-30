@echo off
REM Human approval desk: double-click, type your name, then approve or reject each pending payment.
REM This is the human-only path that moves cash; agents can never run it.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m backend.approve interactive
echo.
pause
