# CyberAgent: Agent-Assisted Network Threat Detection and Investigation using Machine Learning

A university ML case-study project for detecting and investigating malicious network flows.

## Overview

This project implements a two-stage system:
1. An ML classifier (LightGBM) detects and classifies malicious network flows.
2. An LLM agent investigates flagged flows with tools and produces an evidence-based structured report.

The LLM never labels traffic and never overrides the ML label; it only investigates and explains.

## Setup

### Prerequisites

- Python 3.13
- Node.js (for frontend)
- uv (Python package installer)
- Git

### Backend

1. Install Python dependencies:
   ```bash
   uv sync
   ```

2. Set up environment variables (copy `.env.example` to `.env` and adjust):
   ```bash
   cp .env.example .env
   ```

### Frontend

1. Install Node.js dependencies:
   ```bash
   cd frontend
   npm install
   ```

## Usage

### Data Preparation

Place the dataset in `data/raw/` as described in the documentation.

### Reduction

Reduce the dataset to a manageable size while preserving rare classes:
```bash
make reduce
```

### Preprocessing

Preprocess the reduced data (this step is typically included in the training pipeline):
```bash
make preprocess
```

### Training

Train the models:
```bash
make train
```

### Hyperparameter Tuning (Optional)

Run Optuna-based hyperparameter tuning:
```bash
make tune
```

### Evaluation

Evaluate the models (per-class metrics, confusion matrices, model comparison, zero-day holdout):
```bash
make evaluate
```

Results land in `results/tables/` (`model_comparison.csv`, `per_class_metrics_all.csv`,
`zero_day_holdout_results.csv`, `evaluation_summary.json`) and `results/figures/`.

### Agent Evaluation

Evaluate the agent:
```bash
make agent-eval
```

## LLM Configuration

The investigation agent is configured entirely through `.env` (see `.env.example`),
no `config.yaml` edits needed:

| Variable | Purpose | Example |
|---|---|---|
| `LLM_BACKEND` | `openai` (any OpenAI-compatible server), `ollama`, or `mock` | `openai` |
| `LLM_BASE_URL` | Endpoint base | `http://localhost:20128/v1` (Omnirouter proxy) |
| `LLM_API_KEY` | Bearer token (masked; keep local) | — |
| `LLM_MODEL` | Model id | `nvidia/qwen3-next-80b-a3b-instruct` |
| `API_PATH_PREFIX` | Deploy-only; mount API under a prefix (e.g. `/api` on Vercel) | `/api` |
| `VITE_API_BASE_URL` | Frontend → API base (e.g. `http://localhost:8000` in dev) | — |

With `mock` (or no `.env`), the agent falls back to a deterministic tool plan so the
pipeline and tests run fully offline. Agent reports are audited by the grounding
verifier (`src/cyberagent/agent/grounding.py`): the ML label is never overridden,
numbers must trace to tool evidence, and failures force `needs_human_review`.

### API

Start the API server:
```bash
make api
```

### Frontend

Start the frontend development server:
```bash
cd frontend
npm run dev
```

### Windows convenience scripts

Double-click (or run) `start.bat` to launch the whole dev stack in two console
windows: the API on `http://127.0.0.1:8010` (8010 avoids Docker Desktop's habit
of owning :8000 on this machine) and the frontend on `http://localhost:5173`,
with `VITE_API_BASE_URL` pointed at the API. The API needs 1-2 minutes to load
the model and dataset before `/health` responds. `stop.bat` terminates both.

### Full Development

Start both API and frontend:
```bash
make dev
```

## Results

Results are saved in the `results/` directory, including:
- `tables/`: CSV and Markdown tables of metrics, label mappings, etc.
- `figures/`: Plots and charts.
- `agent_logs/`: JSONL logs of agent tool calls.

## Makefile Targets

- `setup`: Install dependencies (backend and frontend)
- `reduce`: Run dataset reduction
- `preprocess`: Run preprocessing
- `train`: Train models
- `tune`: Run hyperparameter tuning
- `evaluate`: Evaluate models
- `agent-eval`: Evaluate agent
- `api`: Start the API server
- `frontend`: Start the frontend development server
- `dev`: Start both API and frontend
- `test`: Run tests
- `lint`: Run linter
- `all`: Run setup, reduce, preprocess, train, evaluate, agent-eval, api, frontend (for development)

## Assumptions and Limitations

### Assumptions
- Dataset is available in the specified format under `data/raw/`.
- Timestamps without AM/PM markers follow the 8:00-17:00 working hours pattern (we infer PM for hours 1-7).
- Benign class can be safely downsampled for training without affecting detection of rare attacks.
- MITRE ATT&CK mappings are available for attack classes present in the dataset.
- LLM backend (OpenAI-compatible proxy / Ollama / mock) is accessible as configured via `.env`.

### Limitations
- The dataset used is the original CIC-IDS2017, which has known labeling and flow-construction issues.
- Timestamps in the dataset lack AM/PM markers; we infer PM for hours 1-7.
- The benign class is downsampled, so benign FPR and precision do not reflect real-world traffic.
- The LLM agent may produce ungrounded claims; the grounding verifier flags them and forces human review, but cannot guarantee semantic faithfulness of prose.
- The evaluation metrics are computed on a reduced, downsampled version of CIC-IDS2017 and are not directly comparable to full-dataset results in the literature.
- The serving API looks flows up by `flow_id` from the processed dataset; live per-packet inference from a sensor is out of scope.
- The anomaly detection module (Isolation Forest) is trained on benign-only data and may not capture all types of anomalies.

## License

MIT