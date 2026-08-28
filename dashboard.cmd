@echo off
rem The operator dashboard. Double-click this from Explorer.
rem
rem It starts a small server on 127.0.0.1 and opens your browser at it. The Accept and
rem Reject buttons run the real litharness commands, so a click writes the same decision
rem row a typed command writes. No model is involved anywhere.
rem
rem Leave this window open while you use the page. Closing it stops the server, and so
rem does the Quit button. Double-clicking a second time just opens another tab.
cd /d "%~dp0"
uv run python tools\dashboard.py --port 8765
if errorlevel 1 (
  echo.
  echo The dashboard stopped with an error. The message above says why.
  pause
)
