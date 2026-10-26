#!/bin/bash
set -e
cd /d/Project/security-network/AUCML
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
echo "[$(date)] STEP preprocess"
uv run python -m scripts.preprocess
echo "[$(date)] STEP train"
uv run python -m scripts.train
echo "[$(date)] STEP evaluate"
uv run python -m scripts.evaluate
echo "[$(date)] PIPELINE DONE"
