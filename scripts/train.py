#!/usr/bin/env python
"""Train the full model zoo (config: training.models) and save to models/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyberagent.logging_setup import logger
from cyberagent.train import main as train_main

if __name__ == "__main__":
    logger.info("=== CyberAgent: train ===")
    train_main()
