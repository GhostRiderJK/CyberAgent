#!/bin/bash
set -e
cd /d/Project/security-network/AUCML
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
echo "[$(date)] STEP preprocess"
uv run python -m scripts.preprocess
echo "[$(date)] STEP evaluate"
uv run python -m scripts.evaluate
echo "[$(date)] STEP agent_eval"
uv run python -m scripts.agent_eval
echo "[$(date)] STEP pytest"
uv run pytest tests/ -q 2>&1 | tail -12
echo "[$(date)] CHAIN DONE"
