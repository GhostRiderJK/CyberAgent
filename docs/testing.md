# Testing — CyberAgent

What is checked automatically, how to run it on Windows, and what no test protects.

## How to run

`make` is not installed here, so use the commands directly. README "Usage" maps 13 of the 15 Makefile
targets (`help` and `all` have no row); `uv run python scripts/tasks.py <target>` wraps most of them
but has no `eval-json` task.

| Check | Command | Run from |
| --- | --- | --- |
| Python suite | `uv run pytest -q` | repo root |
| Frontend unit tests | `npm test` (→ `vitest run`) | `frontend/` |
| Types | `npx tsc -b` | `frontend/` |
| Lint | `npm run lint` (→ `oxlint`) | `frontend/` |
| Production build | `npm run build` (runs `prebuild` → `node scripts/sync-eval.mjs`, then `tsc -b`, then `vite build`) | `frontend/` |

There is no pytest section in `pyproject.toml`; discovery is the default `tests/` layout.

## Python suite — 110 passing

Measured on 2026-10-26: `uv run pytest -q` → `110 passed in 15.58s`, no skips. 107 test functions
exist; `test_normalize_label_variants_and_idempotent` is parametrized over 4 spellings
(`tests/test_preprocess_selection.py:14-16`), which accounts for the other three.

| File | Tests | What it pins down |
| --- | --- | --- |
| `test_preprocess_selection.py` | 21 | label cleanup and grouping, `clean_data` row accounting, split alignment by flow id, holdout removal, time-aware split, train-only fitting, `example_preprocessing_pipeline` end to end on a monkeypatched frame |
| `test_preprocess.py` | 14 | `clean_data` variants, `apply_label_grouping`, `split_data`, `preprocess_train_fit`/`transform`, `handle_imbalance` |
| `test_preprocess_updated.py` | 13 | a near-duplicate of the file above: same 13 test names minus `test_split_determinism` |
| `test_evaluation_artifact.py` | 11 | loads `scripts/build_evaluation_json.py` by path (`importlib`, line 18) and checks re-derivation, both self-check refusals, label/matrix shape, PR-curve ordering and bounds, and the committed artifact |
| `test_feature_selection.py` | 11 | constant and correlated drops, top-k by label, transform-before-fit, no mutation of input, determinism, CSV report, threshold-of-1 disables pruning |
| `test_grounding.py` | 8 | a grounded report passes; overridden label, invented number, fake tool reference and invented endpoint each fail; endpoints from the flow record or tool evidence pass |
| `test_llm_json.py` | 6 | plain, fenced and padded JSON parse; truncated array recovers earlier keys; truncated first string and no-JSON raise |
| `test_data_loader.py` | 5 | `normalize_label`, synthetic frame schema, load paths that must error when files are absent |
| `test_review_policy.py` | 4 | high-impact class is reviewed even at full confidence, low-confidence reason states the number, thin evidence reports the tool count, confident benign needs no review |
| `test_loader_label_cleanup.py` | 4 | loader-side `normalize_label`, duplicate-column drop, synthetic frame shape and `load_data` over it |
| `test_evaluate.py` | 3 | `calculate_metrics`, `compare_models`, `save_evaluation_results` |
| `test_reduce_dataset.py` | 3 | `reduce_dataset`, `save_reduced_dataset`, `load_and_reduce_data` |
| `test_smoke.py` | 2 | `config`, `logging_setup` and `seed` import; `get_seed()` is an int and `set_global_seed` runs |
| `test_config.py` | 1 | `config.yaml` loads through the `config` singleton |
| `test_determinism.py` | 1 | two `split_data` calls with `seed=42` over the reduced data return the same indices |

## Frontend — 31 passing, 5 files

`npm test` on 2026-10-26: `Test Files 5 passed (5)`, `Tests 31 passed (31)`, duration 211 ms.
`src/lib/investigation.test.ts` 7, `src/simulation/engine.test.ts` 9, `src/models/evaluation.test.ts` 6,
`src/lib/format.test.ts` 5, `src/lib/classLabels.test.ts` 4. On the same day `npx tsc -b` exited 0 with
no output and `npm run lint` reported 0 warnings and 0 errors on 51 files.

## Invariants enforced outside the test runner

1. `scripts/build_evaluation_json.py` recomputes accuracy, weighted precision/recall/F1 and macro F1
   from the confusion matrix and refuses to write when they disagree (accuracy tolerance `1e-6`).
2. `frontend/scripts/sync-eval.mjs` writes an `{available: false, reason, command, requires}` record
   instead of copying a stale file, and it runs in `prebuild`, so a build cannot silently ship old
   numbers.
3. `src/models/evaluation.test.ts` re-checks matrix accuracy against the reported headline in the
   bundle that ships, guarded by `isReady(evaluation)` so it skips itself when the artifact is absent.
4. `tests/conftest.py:16-72` hashes every file under `data/processed` and `results/tables` before the
   session and fails after it if any file changed, appeared or disappeared.
5. The confusion-matrix card recomputes accuracy from its own cells and prints a red pill when it
   disagrees (`components/model-results/ConfusionMatrixTable.tsx:31`).

## Manual harness that is not pytest

`uv run python -m scripts.agent_eval` runs the investigation agent over `SAMPLE_PER_CLASS = 3` flows
per class and writes `results/tables/agent_eval_summary.json` plus a JSONL log under
`results/agent_logs/` (gitignored). The committed summary records 33 flows with label fidelity,
grounding pass rate and schema validity all 1.0, `max_tool_calls_used` 5 and
`llm_backend: "configured"` — that run used a live LLM, so the mock path is not what those numbers
describe. `scripts/poc.py` is the end-to-end detector-plus-tool-calling demonstration.

## What has no automated test

- Browser behaviour. `frontend/package.json` devDependencies contain no jsdom, no
  `@testing-library/*` and no Playwright, so no component is rendered in a test. Route correctness,
  the SSE stream in `InvestigationView` and the replay keyboard controls are checked by hand.
- The API. Nothing under `tests/` imports `cyberagent.api` or uses `TestClient`; `/health`, `/predict`,
  `/flow/{id}` and `/investigate` have no request-level test.
- `train.py`, `tune.py`, `anomaly.py`, `explain.py` and `investigation.py` are not imported by any test
  file, so a broken signature in those modules is only caught when the pipeline runs.
- Real-LLM answer quality. `test_llm_json.py` tests the parser, not a model.

## Machine quirks that break runs, not code

- Run the Python suite with nothing else executing. A training or evaluation process alongside
  `uv run pytest -q` has crashed the interpreter here (exit 139, native library contention).
- Start pytest from the repo root, or the `conftest.py` guard hashes the wrong relative paths and
  proves nothing.
- `data/processed/*.parquet` and `models/*.joblib` are gitignored (`.gitignore:75-76`), so
  `test_determinism.py:24` and `test_preprocess.py:530` need `reduce` and `preprocess` to have run.
- Use `uv run python`, never bare `python`: the bare interpreter has no pyarrow and cannot read parquet.
- The older `import magic` hang is history: nothing under `src/`, `scripts/` or `tests/` imports it.

## Before merging

`uv run pytest -q`, then in `frontend/`: `npm test`, `npx tsc -b`, `npm run lint`, `npm run build`.
Report the actual counts, and re-check every number quoted in the docs against an artifact.
