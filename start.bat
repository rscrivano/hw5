@echo off
REM FULL RUN: resets data\campus_customs_new.db from the original, then the agent team works every open ticket.
REM Approve or reject payment requests afterwards with:  .venv\Scripts\python.exe -m backend.approve list
cd /d "%~dp0"
call .venv\Scripts\activate.bat
if "%PORTKEY_API_KEY%"=="" if not exist .env echo WARNING: PORTKEY_API_KEY is not set and there is no .env file - agent calls will fail.
python -m backend.run --all
pause
