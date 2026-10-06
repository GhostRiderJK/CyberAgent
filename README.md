# CyberAgent: Agent-Assisted Network Threat Detection and Investigation using Machine Learning

A university ML case-study project for detecting and investigating malicious network flows.

## Overview

This project implements a two-stage system:
1. An ML classifier (LightGBM) detects and classifies malicious network flows.
2. An LLM agent investigates flagged flows with tools and produces an evidence-based structured report.

The LLM never labels traffic and never overrides the ML label; it only investigates and explains.

## Setup

### Prerequisites

- Python 3.11
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

Evaluate the models:
```bash
make evaluate
```

### Agent Evaluation

Evaluate the agent:
```bash
make agent-eval
```

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
- LLM backend (Anthropic/Ollama/mock) is accessible as configured.

### Limitations
- The dataset used is the original CIC-IDS2017, which has known labeling and flow-construction issues.
- Timestamps in the dataset lack AM/PM markers; we infer PM for hours 1-7.
- The benign class is downsampled, so benign FPR and precision do not reflect real-world traffic.
- The LLM agent may produce ungrounded claims; a grounding verifier is included to mitigate this.
- This project uses synthetic data for testing and a mock LLM backend; real API keys are required for full functionality.
- The model training and tuning steps can be computationally intensive.
- The explanation module (SHAP) is currently a placeholder and may not be fully integrated.
- The anomaly detection module (Isolation Forest) is trained on benign-only data and may not capture all types of anomalies.
- The evaluation metrics are computed on a test set that may not be fully representative of real-world traffic.

## License

MIT