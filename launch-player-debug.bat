@echo off
setlocal
cd /d "%~dp0"
set "PLAYER_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PLAYER_PY%" set "PLAYER_PY=C:\Users\emadg\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
"%PLAYER_PY%" -m elilain_player %*
pause
endlocal
