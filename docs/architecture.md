# Architecture — CyberAgent

How the code is arranged, how data moves, and why the awkward decisions were made. Working rules are
in `AGENTS.md`, requirement status in `docs/prd.md`.

## Offline pipeline

Run in order; each step writes what the next reads. `make` is absent here, so use the README "Usage"
commands, or `uv run python scripts/tasks.py <target>` — it mirrors the Makefile chain except
`eval-json`, which has to be run directly.

```
data/raw/ (CIC-IDS2017 CSVs, gitignored)
   |  scripts/reduce_dataset.py: load_traffic_labelling_data() + reduce_dataset(), caps and seed
   |  from config (reduction.benign_cap 200000, attack_cap 50000, seed 42)
   v
data/processed/flows_features.parquet (389,616 rows) + flows_meta.parquet
   |  scripts/preprocess.py -> example_preprocessing_pipeline(save_outputs=True): load_reduced_data()
   |  reads those same two files, then label grouping, clean, zero-day holdout pull-out, stratified
   |  70/15/15 (split.seed 42), preprocess_train_fit() on X_train only (constant drop, correlation
   |  prune at 0.95, mutual-information top-k=40)
   v
data/processed/holdout_zero_day{,_meta}.parquet (47 flows), preprocess_artifacts.joblib (imputer,
scaler, feature mask, two name lists), results/tables/selected_features.csv (kept|dropped per feature)
   |  scripts/train.py -> train.main(): train_all_models, save_models_and_results, then best-effort
   |  log_to_mlflow (its failure is only a warning line)
   v
models/*.joblib + models/metrics.json + models/best_model_info.json
   |  scripts/evaluate.py -> src/cyberagent/evaluate.py
   v
results/tables/{model_comparison,per_class_metrics_*,label_mapping}.*, results/figures/*.png and
evaluation_summary.json (11x11 matrices, PR/ROC arrays, 99,118,347 bytes committed)
   |  scripts/build_evaluation_json.py  (re-derives from the matrix, self-checks, refuses)
   v
artifacts/eval/evaluation.json (200,179 bytes; the only metrics file the UI trusts)
   |  npm run sync:eval -> frontend/scripts/sync-eval.mjs (also runs in prebuild)
   v
frontend/src/data/evaluation.json (196,309 bytes, imported as text with ?raw)
```

## Online request path

```
browser (React; Vite dev on :5173; start.bat sets VITE_API_BASE_URL=http://127.0.0.1:8010)
   |  GET /health                  -> TopBar and the Overview health card
   |  POST /predict {flow_id}      -> predict_proba()
   |  GET  /flow/{flow_id}         -> get_flow_record()
   |  POST /investigate {flow_id}  -> SSE: start, progress*, end | error
   v
src/cyberagent/api/main.py, with a lazy boot in investigation._initialize_data_and_model(): the two
processed parquets, selected_features.csv, preprocess_artifacts.joblib, models/lightgbm.joblib
(hardcoded path; trains and saves one if absent), then TreeExplainer on a 100-row background
   v
InvestigationAgent.investigate_flow()
   1. predict_proba                    always first; the authoritative label
   2. evidence: the LLM picks tools when a backend is configured, else _run_fallback_plan.
      MAX_TOOL_CALLS = 6 with attempts capped at 8, _is_repeat_call rejects a tool+args pair already
      run, fewer than 2 gathered calls finishes on the fixed plan. _normalize_args forces flow_id and
      label to trusted values, sets time_window_minutes=30 and k=5, drops unknown kwargs.
   3. _synthesize_verdict: template fields plus an optional LLM narrative, then verify_grounding()
      (ml_label_not_overridden, confidence_grounded, numbers_grounded, tool_references_valid,
      identifiers_grounded), the needs_human_review policy, the MITRE lookup.
```

`/investigate` runs the blocking work in a `ThreadPoolExecutor(max_workers=4)` and pushes progress to
the SSE generator with `loop.call_soon_threadsafe`.

## Where each page gets its data

| Page | Source | Live? |
| --- | --- | --- |
| `/` Overview | fixture rows and counts from `mocks/alerts.ts`, real `GET /health`, best macro F1 from the artifact | Mixed, labelled |
| `/alerts` | `mocks/alerts.ts` plus "Simulated" rows from the `state/demoAlerts*` bridge | No |
| `/investigation` | `POST /investigate` SSE over stored flows | Real inference over stored data, no live traffic |
| `/model-results` | `src/data/evaluation.json` only | Artifact, not a stream |
| `/replay` | `mocks/replay.ts`; start/pause is deliberately disabled | No |
| `/simulation` | `src/simulation/` engine, seeded in the browser | No, and it never claims to be |

## Module ownership (backend)

- `config.py` is the `config` singleton over `config.yaml`, `seed.py` sets numpy/random/(optional
  torch) seeds, `logging_setup.py` the `logger`. `data_loader.py` reads raw CSVs, `normalize_label`
  fixes the corrupted-dash spellings, `generate_synthetic_data` returns a schema-compatible frame.
- `preprocess.py` — label grouping, `clean_data`, holdout pull-out, `split_data`, selection fitting,
  `handle_imbalance`, `example_preprocessing_pipeline`, the 11-class `EXPECTED_SUPERVISED_LABELS`.
  `feature_selection.py` has `FeatureSelector` (constant drop, correlation prune at 0.95, then mutual
  information or tree importance, fitted on train only). `features.py` is a 6-line placeholder nothing imports.
- `train.py` — one `train_*` per model (`n_jobs=-1` in the estimators), `train_all_models`,
  `save_models_and_results`, `log_to_mlflow`. `tune.py` is the Optuna search, off in `config.yaml`.
  `evaluate.py` has `calculate_metrics`, `compare_models`, the plot functions, `save_evaluation_results`.
- `anomaly.py` — Isolation Forest train/predict/save/load and a demo `main()`. Nothing imports it, no
  script calls it, the API cannot reach it, no test covers it; `evaluate.py:141` only skips an
  `isolation_forest*` file while gathering supervised models. `save_anomaly_model` is the only writer of
  `models/isolation_forest{,_scaler}.joblib`, and those ignored files sit on disk, so the module was run
  by hand. This is where a zero-day companion metric would go; the choice is still open.
- `explain.py` — `explain_model` picks `shap.TreeExplainer` for tree models, `KernelExplainer` else.
  `investigation.py` — the five tools, `get_flow_record`, the lazy boot above.
- `agent/investigation_agent.py` — loop, `_normalize_args`, `_run_fallback_plan`, verdict synthesis.
  `agent/grounding.py` — the five checks. `llm.py` — env-driven client, mock default.
- `api/models.py` — Pydantic shapes; `api/main.py` — routes; `api/__main__.py` — uvicorn on `api.host`,
  `0.0.0.0` by default, which is why `start.bat` overrides to 127.0.0.1.

## Frontend layout

`App.tsx` routes to the four page components in `components/`, `pages/Overview.tsx`,
`pages/Simulation.tsx` and `components/simulation/*`. Below them: `components/shared/*` for chrome,
`components/ui/*` for primitives, `services/{api,useApiHealth}.ts`, the simulation-to-alerts bridge in
`state/demoAlerts*.ts`, fixtures in `mocks/{alerts,replay}.ts`, pure helpers in
`lib/{classLabels,format,investigation}.ts` (each with a co-located Vitest file) and
`models/evaluation.ts`. The engine in `src/simulation/` imports no React, so Vitest runs it in Node.

## Decisions and why

- **Classifier is authoritative.** A label is a measurable output; a narrative is not. Letting the LLM
  relabel makes every downstream number untraceable, so nothing in the agent's output schema can
  propose a label and `ml_label_not_overridden` fails the run when prose disagrees.
- **Macro F1 picked the model, not accuracy.** BENIGN is 29,158 of the 53,342 test rows, so accuracy
  flatters a lazy classifier. LightGBM wins on macro F1 (0.995273) and is the fastest tree model here:
  29.826 ms per 1000 samples against 52.85 (XGBoost) and 373.33 (random forest).
- **One self-checking artifact instead of hand-typed numbers.** The old model-results page carried
  metrics whose matrix did not sum to its own accuracy. `build_evaluation_json.py` recomputes accuracy,
  weighted precision/recall/F1 and macro F1 from the confusion matrix and aborts on disagreement
  (1e-6 on accuracy); `src/models/evaluation.test.ts` re-checks the invariant inside the bundle.
  Trade-off: the JSON ships inside the JS, so the app builds to one 951.58 kB chunk (gzip 235.06 kB).
  Code-splitting is the known fix and has not been done.
- **SHAP at investigation time.** Per-sample probabilities and explainer outputs are not persisted, so
  `investigation.py` builds the `TreeExplainer` on `_features_df_model.head(100)` at boot; measured
  here, `_initialize_data_and_model()` took 0.8 s on a warm file cache (2026-10-26). The reason is
  consistency, not speed: explanations come from the model actually loaded, never a stale dump.
- **Structured data end to end.** An earlier version flattened tool results into prose and parsed them
  back, so the SHAP panel read "No explanation data" under a verdict quoting SHAP numbers.
  `explain_flow` now returns parallel arrays plus `value_scale` and `explanation_error`, the agent
  reshapes them into `shap_explanation`, and `src/lib/investigation.ts` parses defensively. Never
  reintroduce prose as a data channel. `value_scale` is always `"standardized"` because served rows are
  post-scaler z-scores from `preprocess_artifacts.joblib`; without it a reader takes `-1.83` for bytes.
- **Simulation is client-side and seeded.** `rng.ts` is a mulberry32 generator and replay state folds
  from the step log instead of mutating, so scrubbing reproduces and a what-if re-run differs only by
  the toggled defense. Rule-based theatre, labelled as such, not RL.
- **Mock LLM by default.** Tests and demos must run with no key, so `LLMClient` defaults to `mock`, its
  `available` is false, and the agent takes the deterministic plan. A `.env` pointing at a live backend
  uses the same path, which is why `scripts/agent_eval.py:82` records which of the two ran.

## Failure behaviour per page

- No artifact → `sync-eval.mjs` writes an "unavailable" record naming
  `python scripts/build_evaluation_json.py`, and `/model-results` prints that command as its empty state.
- Missing `models/lightgbm.joblib` → the boot runs `example_preprocessing_pipeline(save_outputs=False)`,
  trains LightGBM, saves it. Missing `preprocess_artifacts.joblib` → only a warning, and serving uses
  raw features while the model expects scaled ones: the quietest, most dangerous failure here.
- Unknown `flow_id` → `predict` 404s with the tool's own message, `/flow/{id}` 404s with the recorded
  reason. Investigation error → SSE `error` carrying `str(exception)`; the verdict path returns
  `predicted_class: "UNKNOWN"` with human review forced.

## Environment constraints that bite

- **No `make`.** The README table gives the command behind 13 of the 15 Makefile targets; only `help`
  and `all` (which chains the whole pipeline) have no row.
- **Run the Python suite alone.** A training or evaluation process alongside `uv run pytest -q` has
  crashed this machine's interpreter (exit 139, native library contention). `start.bat` pins
  `OMP_NUM_THREADS=1` for the API and `n_jobs=-1` sits in the estimators. `seed.py` tries to import
  torch, which is not installed in this venv, and ignores the failure.
- **`libmagic`.** An older suite run hung on `import magic`; `libmagic.dll` plus `magic.mgc` in the run
  directory fixed it. Nothing under `src/`, `scripts/` or `tests/` imports `magic` now, so this is a
  machine note rather than a project requirement.
- **Windows paths.** `tests/conftest.py` hashes `data/processed` and `results/tables` relative to the
  current directory, so pytest must start from the repo root or the integrity guard proves nothing.
  Files named with U+F03A (see `AGENTS.md` open items) cannot be matched by a literal pathspec.
