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
echo Wait for "Uvicorn running on http://127.0.0.1:8010" in the API window, then
echo open http://localhost:5173. /health answers as soon as uvicorn is listening;
echo the model, the processed features and the SHAP explainer load on the first
echo request that needs them (/model/status, /flow, /predict or Investigate) -
echo measured 0.85 s on 2026-10-26. The agent's LLM backend comes from .env; if
echo that endpoint is unreachable it falls back to the deterministic tool plan,
echo so an investigation still completes.
