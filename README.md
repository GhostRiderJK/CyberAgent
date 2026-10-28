# CyberAgent: Agent-Assisted Network Threat Detection and Investigation using Machine Learning.

A university ML case-study project for detecting and investigating malicious network flows.

## Overview

This project implements a two-stage system:
1. An ML classifier (LightGBM) detects and classifies malicious network flows.
2. An LLM agent investigates flagged flows with tools and produces an evidence-based structured report.

The LLM never labels traffic and never overrides the ML label; it only investigates and explains.

## System Architecture

Two halves: an offline pipeline that produces the numbers the UI is allowed to show, and an online
request path that investigates one stored flow at a time.

```
data/raw/ (CIC-IDS2017 CSVs, not in the repo)
  -> scripts/reduce_dataset.py       data/processed/flows_features.parquet + flows_meta.parquet
  -> scripts/preprocess.py           data/processed/preprocess_artifacts.joblib (imputer, scaler,
                                     feature mask, two name lists) + holdout_zero_day.parquet
                                     stratified 70/15/15, seed 42, 40 features kept
  -> scripts/train.py                models/*.joblib, models/metrics.json, best_model_info.json
  -> scripts/evaluate.py             results/tables/*, results/figures/*, evaluation_summary.json
  -> scripts/build_evaluation_json.py  artifacts/eval/evaluation.json; recomputes every metric from
                                     the confusion matrix and refuses to write when they disagree
  -> npm run sync:eval               frontend/src/data/evaluation.json -> /model-results
```

```
React frontend (Vite :5173) -> FastAPI (config :8000, start.bat :8010)
  GET  /health, /model/status, /
  POST /predict        {flow_id}  -> predict_proba()
  GET  /flow/{flow_id}            -> connection-level fields of the stored record
  POST /investigate    {flow_id}  -> SSE: start, progress*, end | error
       -> InvestigationAgent: predict_proba first, then at most 6 calls from
          {predict_proba, explain_flow, find_related_flows, similar_known_attacks,
           lookup_attack_pattern}. Tool names are checked against the registry and every
          argument is re-pinned to trusted values before the tool runs.
       -> verdict synthesis -> grounding verifier (5 checks) -> heuristic MITRE lookup
```

Boot is lazy: the first request loads the two processed parquets, `results/tables/selected_features.csv`,
`preprocess_artifacts.joblib` and `models/lightgbm.joblib`, then builds a SHAP `TreeExplainer` over a
100-row background. Explanations therefore come from the model actually loaded, never from a stale
dump, and `explain_flow` answers with parallel arrays (`shap_values[]`, `feature_names[]`,
`feature_values[]`, the top 10 by absolute effect) plus `value_scale: "standardized"`, because served
rows are post-scaler z-scores. `/investigate` runs in a four-worker thread pool and pushes progress
events back onto the event loop.

Layout: backend in `src/cyberagent/` (`config`, `seed`, `data_loader`, `features`, `preprocess`,
`feature_selection`, `train`, `tune`, `evaluate`, `anomaly`, `explain`, `investigation`, `llm`, `agent/` for the loop and
grounding, `api/` for routes and request/response shapes). Frontend in `frontend/src/` (`components/`,
`pages/`, `services/`, `lib/` for class labels, formatting and the defensive investigation parse,
`models/evaluation.ts`, `simulation/` as a pure TypeScript engine with no React import, `mocks/` for
the labelled fixtures). No route serves metric files: the browser reads only the synced artifact.

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
| `LLM_BACKEND` | `ollama` (native `/api/chat`), `openai` (any OpenAI-compatible server), or `mock` | `ollama` |
| `LLM_BASE_URL` | Endpoint base; unset falls back to `http://localhost:11434` for `ollama` | `http://localhost:11434` |
| `LLM_API_KEY` | Bearer token (masked; keep local) | — |
| `LLM_MODEL` | Model id, for Ollama the name of a model you have pulled | `llama3.2:3b` |
| `API_PATH_PREFIX` | Deploy-only; mount the API under a path prefix when a proxy keeps that prefix | `/api` |
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
with `VITE_API_BASE_URL` pointed at the API. `/health` responds as soon as
uvicorn is listening; the model, the processed features and the SHAP explainer
load on the first request that needs them, measured at 0.85 s on 2026-10-26.
`stop.bat` terminates both.

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
- **Not live traffic.** Agents are hand-written rule-based policies, not
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

- [AGENTS.md](AGENTS.md) — the project guide: environment rules, working rules and the data facts.
  Read it before changing code.
- [docs/prd.md](docs/prd.md) — what the system is required to do, requirement by requirement, with the
  status of each.
- [docs/architecture.md](docs/architecture.md) — how the code is arranged, how data moves through the
  offline pipeline and the request path, and why the awkward decisions were made.
- [docs/testing.md](docs/testing.md) — how to run every check on Windows, what the 110 Python and 31
  frontend tests pin down, and what no test covers.

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

## License

MIT
