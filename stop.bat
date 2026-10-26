@echo off
rem ============================================================
rem  Stops the CyberAgent dev stack (API on :8010, frontend on :5173)
rem  started by start.bat. Safe to run even if only one is up.
rem ============================================================

set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8010" ^| findstr LISTENING') do (
  echo Stopping API, pid %%p ...
  taskkill /pid %%p /f /t >nul
  set FOUND=1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr LISTENING') do (
  echo Stopping frontend, pid %%p ...
  taskkill /pid %%p /f /t >nul
  set FOUND=1
)

if "%FOUND%"=="0" echo Nothing listening on 8010 or 5173 - stack already stopped.
if not "%FOUND%"=="0" echo Stopped. You can close any remaining "CyberAgent" console windows.
