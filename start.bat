@echo off
rem Starts the family page. Keep this window open while you're shopping; close it to stop.
cd /d "%~dp0"
if not exist "config.json" (
  echo No config.json yet. Run setup.bat first.
  pause
  exit /b 1
)
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" car_agent.py serve --share
pause
