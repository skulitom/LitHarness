@echo off
rem The operator dashboard. Double-click this from Explorer: it regenerates
rem dashboard.html from the repository and opens it in the default browser.
rem Read-only. It makes no model calls and never writes to a database.
cd /d "%~dp0"
uv run python tools\dashboard.py
if errorlevel 1 (
  echo.
  echo The dashboard could not be generated. The message above says why.
  pause
  exit /b 1
)
start "" "dashboard.html"
