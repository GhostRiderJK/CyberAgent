#!/usr/bin/env python
"""Run Optuna hyperparameter tuning (config: tuning.*) and save best params."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyberagent.logging_setup import logger
from cyberagent.tune import main as tune_main

if __name__ == "__main__":
    logger.info("=== CyberAgent: tune ===")
    tune_main()
