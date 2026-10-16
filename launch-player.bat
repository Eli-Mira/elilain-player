@echo off
setlocal
cd /d "%~dp0"
set "PLAYER_PY=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PLAYER_PY%" set "PLAYER_PY=C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
if not exist "%PLAYER_PY%" (
  echo Python environment not found. Use launch-player-debug.bat after installing dependencies.
  pause
  exit /b 1
)
start "" "%PLAYER_PY%" -m elilain_player
endlocal
