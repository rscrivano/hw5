@echo off
REM One-time setup: Python virtual env + packages. Pause OneDrive syncing while this runs.
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python reset_db.py
echo.
echo Setup done. Run start.bat for a full agent run.
pause
