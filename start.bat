@echo off
rem ============================================================
rem  CyberAgent dev stack launcher
rem  API      -> http://127.0.0.1:8010  (port 8010 avoids the
rem             Docker Desktop proxy that often owns :8000)
rem  Frontend -> http://localhost:5173
rem  Stop everything with stop.bat
rem ============================================================
cd /d %~dp0

echo Starting API on http://127.0.0.1:8010 ...
start "CyberAgent API" cmd /k "cd /d %~dp0 && set OMP_NUM_THREADS=1&& uv run uvicorn cyberagent.api.main:app --host 127.0.0.1 --port 8010"

echo Starting frontend on http://localhost:5173 ...
start "CyberAgent Frontend" cmd /k "cd /d %~dp0frontend && set "VITE_API_BASE_URL=http://127.0.0.1:8010" && npm run dev"

echo.
echo Both started in separate windows.
echo NOTE: the API loads the model and dataset on boot - give it 1-2 minutes
echo       (watch the "CyberAgent API" window), then open http://localhost:5173
echo       and click Investigate. Run "make api" style checks on :8010.
