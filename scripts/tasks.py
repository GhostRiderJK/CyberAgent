#!/usr/bin/env python
"""
Cross-platform task runner for CyberAgent.
Mirrors the Makefile targets.
"""
import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and stream output."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result

def task_setup():
    """Install dependencies."""
    print("Setting up dependencies...")
    run_command("python -m uv sync")
    # Also install frontend dependencies
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        run_command("npm install", cwd=frontend_dir)

def task_reduce():
    """Run dataset reduction."""
    print("Reducing dataset...")
    run_command("python -m uv run python -m scripts.reduce_dataset")

def task_preprocess():
    """Run preprocessing."""
    print("Running preprocessing...")
    run_command("python -m uv run python -m scripts.preprocess")

def task_train():
    """Run model training."""
    print("Training models...")
    run_command("python -m uv run python -m scripts.train")

def task_tune():
    """Run hyperparameter tuning."""
    print("Running hyperparameter tuning...")
    run_command("python -m uv run python -m scripts.tune")

def task_evaluate():
    """Run model evaluation."""
    print("Evaluating models...")
    run_command("python -m uv run python -m scripts.evaluate")

def task_agent_eval():
    """Run agent evaluation."""
    print("Evaluating agent...")
    run_command("python -m uv run python -m scripts.agent_eval")

def task_api():
    """Start the API server."""
    print("Starting API server...")
    run_command("python -m uv run python -m cyberagent.api")

def task_frontend():
    """Start the frontend development server."""
    print("Starting frontend...")
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        run_command("npm run dev", cwd=frontend_dir)
    else:
        print("Frontend directory not found!")
        sys.exit(1)

def task_dev():
    """Start both API and frontend (for development)."""
    print("Starting development servers...")
    # We'll start API in background, then frontend
    import threading
    import time

    def start_api():
        run_command("python -m uv run python -m cyberagent.api")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    # Give API a moment to start
    time.sleep(2)

    # Start frontend (this will block)
    task_frontend()

def task_test():
    """Run tests."""
    print("Running tests...")
    run_command("python -m uv run pytest")

def task_lint():
    """Run linter."""
    print("Running linter...")
    run_command("python -m uv run ruff check")

def task_fix_labels():
    """Fix labels in existing parquet files by normalizing and regrouping."""
    print("Fixing labels in existing parquet files...")
    from src.cyberagent.preprocess import load_reduced_data, apply_label_grouping
    import pandas as pd
    import os

    # Load the existing data
    features_df, metadata_df = load_reduced_data()

    # Apply label normalization and grouping
    features_df, metadata_df, label_mapping = apply_label_grouping(features_df, metadata_df)

    # Save back to the same files (in place)
    from src.cyberagent.config import config
    processed_dir = config.get("dataset.processed_dir")
    features_path = f"{processed_dir}/flows_features.parquet"
    metadata_path = f"{processed_dir}/flows_meta.parquet"

    # Ensure directory exists
    from pathlib import Path
    Path(features_path).parent.mkdir(parents=True, exist_ok=True)

    # Save the fixed data
    features_df.to_parquet(features_path, compression='zstd')
    metadata_df.to_parquet(metadata_path, compression='zstd')

    # Log file sizes
    features_size = os.path.getsize(features_path) / (1024 * 1024)  # MB
    metadata_size = os.path.getsize(metadata_path) / (1024 * 1024)  # MB
    print(f"Fixed features file size: {features_size:.2f} MB")
    print(f"Fixed metadata file size: {metadata_size:.2f} MB")

    print(f"Label mapping applied: {label_mapping}")
    print("Labels fixed successfully!")


def task_all():
    """Run full pipeline: setup, reduce, preprocess, train, evaluate, agent-eval, api, frontend."""
    print("Running full pipeline...")
    task_setup()
    task_reduce()
    task_preprocess()
    task_train()
    task_tune()  # Optional, but we'll run it
    task_evaluate()
    task_agent_eval()
    # For dev, we don't start API and frontend here as they block
    # Instead, we'll just note they need to be started manually
    print("Pipeline completed. To start API and frontend, run:")
    print("  python scripts/tasks.py api")
    print("  python scripts/tasks.py frontend")
    print("Or for both: python scripts/tasks.py dev")

def print_help():
    """Print help message."""
    print("""
CyberAgent Task Runner

Usage: python scripts/tasks.py <task>

Tasks:
  setup     - Install dependencies (backend and frontend)
  reduce    - Run dataset reduction
  preprocess- Run preprocessing
  train     - Train models
  tune      - Run hyperparameter tuning
  evaluate  - Evaluate models
  agent-eval- Evaluate agent
  api       - Start the API server
  frontend  - Start the frontend development server
  dev       - Start both API and frontend (for development)
  test      - Run tests
  lint      - Run linter
  all       - Run full pipeline (setup, reduce, preprocess, train, tune, evaluate, agent-eval)
  help      - Show this help message

Examples:
  python scripts/tasks.py setup
  python scripts/tasks.py reduce
  python scripts/tasks.py dev
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    task = sys.argv[1].lower()

    if task == "setup":
        task_setup()
    elif task == "reduce":
        task_reduce()
    elif task == "preprocess":
        task_preprocess()
    elif task == "train":
        task_train()
    elif task == "tune":
        task_tune()
    elif task == "evaluate":
        task_evaluate()
    elif task == "agent-eval":
        task_agent_eval()
    elif task == "api":
        task_api()
    elif task == "frontend":
        task_frontend()
    elif task == "dev":
        task_dev()
    elif task == "test":
        task_test()
    elif task == "lint":
    elif task == "fix-labels":
        task_fix_labels()
        task_lint()
    elif task == "all":
        task_all()
    elif task == "help":
        print_help()
    else:
        print(f"Unknown task: {task}")
        print_help()
        sys.exit(1)