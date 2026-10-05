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

### Training

Train the models:
```bash
make train
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

## Limitations

- The dataset used is the original CIC-IDS2017, which has known labeling and flow-construction issues.
- Timestamps in the dataset lack AM/PM markers; we infer PM for hours 1-7.
- The benign class is downsampled, so benign FPR and precision do not reflect real-world traffic.
- The LLM agent may produce ungrounded claims; a grounding verifier is included to mitigate this.
- This project uses synthetic data for testing and a mock LLM backend; real API keys are required for full functionality.

## License

MIT
