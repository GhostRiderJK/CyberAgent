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

> **`make` is not installed on the development machine (Windows).** Each target below is listed with
> the command it actually runs, so any step can be run without Make:
>
> | Target | Underlying command |
> | --- | --- |
> | `setup` | `uv sync`, then `cd frontend && npm install` |
> | `reduce` | `uv run python -m scripts.reduce_dataset` |
> | `preprocess` | `uv run python -m scripts.preprocess` |
> | `train` | `uv run python -m scripts.train` |
> | `tune` | `uv run python -m scripts.tune` (skipped by default: `tuning.enabled: false` in `config.yaml`) |
> | `evaluate` | `uv run python -m scripts.evaluate` |
> | `eval-json` | `uv run python scripts/build_evaluation_json.py` |
> | `agent-eval` | `uv run python -m scripts.agent_eval` |
> | `api` | `uv run python -m cyberagent.api` |
> | `frontend` | `cd frontend && npm run dev` |
> | `dev` | start `uv run python -m cyberagent.api`, then `cd frontend && npm run dev` in a second terminal |
> | `test` | `uv run pytest -q`, plus `cd frontend && npm test` |
> | `lint` | `uv run ruff check`, plus `cd frontend && npm run lint` |

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

#### Evaluation artifact for the frontend

The Model Results page renders **only** from one generated file, `artifacts/eval/evaluation.json`:

```bash
make evaluate     # produces models/metrics.json and results/tables/evaluation_summary.json
make eval-json    # builds artifacts/eval/evaluation.json from them
cd frontend && npm run sync:eval    # copies it to frontend/src/data/evaluation.json
```

`npm run build` runs `sync:eval` first (`prebuild`). `build_evaluation_json.py` re-derives accuracy,
weighted precision/recall/F1 and macro F1 from the stored confusion matrix and aborts if any of them
disagrees with the reported value, if the matrix is not square over the label list, if its cell total
is not the test-sample count, or if a precision-recall point leaves `[0, 1]`. Nothing is rounded into
place to make a check pass; a failed self-check is a build failure. If the models or the split are
missing, the script names the exact command to regenerate them and stops.

What these numbers do **not** show:

- They describe a stratified random split of CIC-IDS2017 (reduced copy in `data/`). Capture days are
  mixed across train and test, so same-day near-duplicate flows can appear on both sides; this is not
  real-world generalisation and not operational-traffic performance.
- BENIGN is ~55% of the split, so accuracy overstates attack performance. Macro F1 and the per-class
  table are the load-bearing numbers.
- Per-sample predicted probabilities and the split indices were not persisted, so PR curves and the
  matrix are rebuilt from the stored evaluation artifacts; rebuilding them from scratch requires
  re-running `make preprocess`, which regenerates the split.
- Precision-recall curves are stored for the selected best model only (one-vs-rest, ≤200 threshold
  points per class, evenly sampled by index, no smoothing or interpolation).
- The zero-day holdout (47 Heartbleed/Infiltration flows) is far too small for a confidence interval,
  and its 0.00% result is a statement about those two families only.

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
numbers must trace to tool evidence, any IP the narrative quotes must appear in the
evidence or the stored flow record, and failures force `needs_human_review`. When
review is required the result also carries `needs_human_review_reason`, so a
100.00%-confidence escalation still explains which rule fired.

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

Frontend unit tests (the simulation engine) and production build:
```bash
cd frontend
npm test     # vitest run
npm run build
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

## Simulation page

The `/simulation` page is a self-contained adversary war game: four attacker
archetypes (opportunist, apt, ransomware, insider) and three defender roles
(SOC analyst, incident responder, threat hunter) act on a fixed six-host,
three-zone network (DMZ / INTERNAL / CRITICAL). It runs entirely in the
browser - the FastAPI backend can be stopped, and the page still works.

- `npm test` (in `frontend/`) runs the Vitest suite over the engine
  (`src/simulation/`), which is pure TypeScript with no React or network calls.
- **Determinism.** All randomness comes from a seeded mulberry32 PRNG
  (`src/simulation/rng.ts`). The same seed + timesteps + network always
  produces a byte-identical `SimulationResult`; the UI exposes both knobs.
- **What you can do.** Run single or swarm mode (N followers per archetype
  across M batch seeds) to get per-host compromise rates, top attack paths,
  defense effectiveness, a vulnerability-priority ranking, and an honest
  convergence note. The War-Game Replay card scrubs the timeline (derived from
  the same step log via `foldSteps`, so it can never disagree with the results),
  and the What-If card lets you toggle MFA/EDR/firewall/patched or remove a CVE
  per host, then re-runs the *same seed* and prints before/after deltas.
  "Send to Alerts as demo flows" pushes 3-6 tagged `Simulated` rows into the
  Alerts table only - fixtures and Model Results stay untouched.
- **Limitations (by design).** Agents are hand-written rule-based policies, not
  trained RL models; probabilities are static heuristics modulated by defenses.
  Nothing here observes real traffic - every screen carries a
  "Simulated - not live traffic" badge - and CVE IDs are illustrative fixtures,
  not verified advisories. Swarm aggregates are reported verbatim, including a
  "not converged" flag when batch drift exceeds 5 percentage points.

## Results

Results are saved in the `results/` directory, including:
- `tables/`: CSV and Markdown tables of metrics, label mappings, etc.
- `figures/`: Plots and charts.
- `agent_logs/`: JSONL logs of agent tool calls.

## Documentation

- [AGENTS.md](AGENTS.md) — the project guide: environment rules, working rules, pipeline and
  limitations. Read it before changing code.
- [docs/prd.md](docs/prd.md) — what the system is required to do, requirement by requirement, with the
  status of each.
- [docs/architecture.md](docs/architecture.md) — how the code is arranged, how data moves through the
  offline pipeline and the request path, and why the awkward decisions were made.
- [docs/design_system.md](docs/design_system.md) — the frontend's implemented visual rules: tokens,
  surfaces, badges, formatters, charts, empty states, accessibility, and where they live.
- [docs/testing.md](docs/testing.md) — how to run every check on Windows, what the 110 Python and 31
  frontend tests pin down, and what no test covers.
- [docs/security.md](docs/security.md) — trust boundaries, the agent's prompt-injection surface, the
  unauthenticated API as configured, and a checklist to work through before exposure.

## Makefile Targets

- `setup`: Install dependencies (backend and frontend)
- `reduce`: Run dataset reduction
- `preprocess`: Run preprocessing
- `train`: Train models
- `tune`: Run hyperparameter tuning
- `evaluate`: Evaluate models
- `eval-json`: Build `artifacts/eval/evaluation.json` for the Model Results page
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