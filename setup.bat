@echo off
rem Family Car Finder setup for Windows: installs what it needs into .venv, then asks a few questions.
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3.10 or newer is needed and wasn't found.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run setup.bat again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a private Python environment in .venv ...
  %PY% -m venv .venv || goto :fail
)
echo Installing dependencies (first time takes a minute) ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :fail

".venv\Scripts\python.exe" setup.py
echo.
pause
exit /b 0

:fail
echo.
echo Setup hit an error above. Check your internet connection and run setup.bat again.
pause
exit /b 1
