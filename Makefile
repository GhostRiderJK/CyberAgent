# CyberAgent Makefile
# Mirrors the functionality of scripts/tasks.py

.PHONY: setup reduce preprocess train tune evaluate eval-json agent-eval api frontend dev test lint all help

# Default target
help:
	@echo "CyberAgent Makefile"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  setup	     Install dependencies (backend and frontend)"
	@echo "  reduce	     Run dataset reduction"
	@echo "  preprocess   Run preprocessing"
	@echo "  train	     Train models"
	@echo "  tune	     Run hyperparameter tuning"
	@echo "  evaluate     Evaluate models"
	@echo "  eval-json    Build artifacts/eval/evaluation.json (frontend's only metrics source)"
	@echo "  agent-eval   Evaluate agent"
	@echo "  api	     Start the API server"
	@echo "  frontend     Start the frontend development server"
	@echo "  dev	     Start both API and frontend (for development)"
	@echo "  test	     Run tests"
	@echo "  lint	     Run linter"
	@echo "  all	     Run full pipeline (setup, reduce, preprocess, train, tune, evaluate, agent-eval)"
	@echo "  help	     Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make setup"
	@echo "  make reduce"
	@echo "  make dev"

setup:
	uv sync
	# Also install frontend dependencies
	cd frontend && npm install

reduce:
	uv run python -m scripts.reduce_dataset

preprocess:
	uv run python -m scripts.preprocess

train:
	uv run python -m scripts.train

tune:
	uv run python -m scripts.tune

evaluate:
	uv run python -m scripts.evaluate

eval-json:
	uv run python scripts/build_evaluation_json.py

agent-eval:
	uv run python -m scripts.agent_eval

api:
	uv run python -m cyberagent.api

frontend:
	cd frontend && npm run dev

dev:
	# Start API in background, then frontend
	@echo "Starting development servers..."
	@uv run python -m cyberagent.api & \
	cd frontend && npm run dev

test:
	uv run pytest

lint:
	uv run ruff check

all: setup reduce preprocess train tune evaluate eval-json agent-eval
	@echo "Pipeline completed. To start API and frontend, run:"
	@echo "  make api"
	@echo "  make frontend"
	@echo "Or for both: make dev"