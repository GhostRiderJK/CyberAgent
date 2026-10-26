# Product requirements — CyberAgent

For a teammate, an evaluator, or the owner in six months. Operational rules for AI assistants
live in `AGENTS.md`; structure in `docs/architecture.md`. This file states what the product is
for and whether each requirement is actually met.

## The problem

A flow classifier's label is not an investigation. "PortScan, 0.997" tells an analyst nothing
about which packets, which neighbour flows, or what to do next, and a model trained on eleven
classes cannot say anything at all about an attack it has never seen.

The obvious fix — let an LLM write the report — trades one failure for a worse one. A free-writing
model invents IP addresses, drifts the confidence number, and can quietly relabel the flow. In a
security tool an invented "confirmed exfiltration" is more damaging than a missing one.

## The answer this project ships

Three separated roles, each with a hard constraint:

- The **classifier decides**. LightGBM's predicted class is authoritative and is the only label
  the system reports.
- The **agent gathers**. It may only call five predefined tools, at most six times, and cannot
  supply its own label or its own numbers.
- The **verifier rejects**. Five grounding checks compare the narrative against the tool evidence
  and the stored flow record; a failed check is listed by name rather than hidden.

So the reader gets the model's answer plus a narrative that has been audited against the evidence
that produced it — and a limitations block that says where both are weak.

## Users

- **Persona the product is aimed at:** a SOC analyst triaging a flagged flow, who needs the label,
  the top contributing features, related flows and known-attack exemplars in one screen.
- **Actual reader today:** the ESE case-study evaluator, and the owner. Nothing is deployed; the
  API serves stored CIC-IDS2017 flows to a local React app. The persona is untested with a real
  analyst.

## Goals

1. Reproducible detection numbers on a held-out split, with every figure traceable to an artifact.
2. An investigation report whose claims are checked mechanically, not just read.
3. Honest presentation: fixtures, mock runs and rule-based simulation labelled as such.
4. Works offline with no key: `uv run pytest -q` and `npm run build` succeed on a machine with no
   LLM reachable.

## Non-goals

Real-time packet capture, intrusion prevention, replacing analysts, production deployment, and any
claim of LLM quality. Live per-packet inference is out of scope by design: the API looks flows up
by `flow_id`.

## Requirements and their real status

| ID | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| R1 | Classify flows into 11 supervised classes | Met | `EXPECTED_SUPERVISED_LABELS`, `src/cyberagent/preprocess.py:511` |
| R2 | Macro F1 ≥ 0.8 on the test split | Met, with a leakage caveat | `evaluation.json`: lightgbm `f1_macro` 0.995273 on 53,342 rows; random stratified split may inflate it |
| R3 | Benign false-positive rate ≤ 5% | Met | BENIGN recall 0.998765 (29,122 of 29,158 correct) in the artifact's confusion matrix |
| R4 | Detect never-seen attack types | **Failed** | 47-flow zero-day holdout: every flow predicted BENIGN, accuracy 0.0 for all five models |
| R5 | Explain a single flow's prediction | Met | `explain_flow` returns top-10 SHAP features with `value_scale: "standardized"`, computed at investigation time |
| R6 | Agent may not override the ML label | Met | `ml_label_not_overridden` grounding check; `tests/test_grounding.py` asserts the failure case |
| R7 | Agent numbers grounded in tool evidence | Met | `numbers_grounded`, `confidence_grounded` (±0.05), `identifiers_grounded`, `tool_references_valid` |
| R8 | Agent run quality measured | Partially | `results/tables/agent_eval_summary.json`: 33 flows, 3 per class, `ml_label_fidelity` 1.0, `grounding_pass_rate` 1.0, `schema_validity` 1.0, `max_tool_calls_used` 5, `llm_backend` "configured". One run, one dataset, no repeated trials |
| R9 | Metrics page cannot show invented numbers | Met | `scripts/build_evaluation_json.py` self-check (accuracy tolerance 1e-6) plus `frontend/src/models/evaluation.test.ts` re-checking diagonal vs reported accuracy |
| R10 | Attack/defence simulation for teaching | Met, illustrative only | `frontend/src/simulation/`, `engine.test.ts` (9 cases); rule-based, seeded, never real traffic |
| R11 | Triage module that auto-archives benign flows | **Not implemented** | No such module in `src/cyberagent/`; `/alerts` shows demo fixtures plus optional simulated rows |
| R12 | MLflow tracking of runs | Partially | `mlruns/` and `mlflow.db` exist locally; `mlflow.db` is untracked run state and `log_to_mlflow` in `src/cyberagent/train.py` has no test |

## How we know it works

- `uv run pytest -q` → 110 passed (23.64 s on the run behind this file).
- `cd frontend && npm test` → 31 passed in 5 files; `npm run lint` → 0 warnings / 0 errors on 51
  files; `npx tsc -b` → exit 0; `npm run build` → succeeds, `prebuild` re-syncs the artifact and
  prints `5 models, 11 classes, 53342 test samples, best=lightgbm`.
- `uv run python scripts/build_evaluation_json.py` → refuses to write if the confusion matrix
  disagrees with any reported metric, and names the missing artifact and its regeneration command
  otherwise.
- `uv run python -m scripts.agent_eval` → the R8 summary above.
- Manual, not scripted: the pages are checked by hand against a running API. `docs/testing.md`
  lists which checks exist and which do not.

## Known weak spots

- R4 is the real finding, not a rough edge: the supervised model is blind to unseen classes and the
  zero-day holdout proves it.
- The 5.7%-detection default run of the simulation (2 detections of 35 actions at timesteps 5,
  seed 42) reads as a broken defender; it is a tuning point, not a bug in the metric.
- Grounding checks are string and number comparisons; prose that is misleading but numerically
  correct still passes.
- `agent_eval` covers 33 of 53,342 flows and one backend configuration.

## Open decisions

1. Whether to add an Isolation Forest score next to the supervised prediction for the holdout, so
   "unseen" has a second opinion. Awaiting the owner's call.
2. Whether to run a split-by-day evaluation to quantify leakage from the random split.
3. Whether to merge `fix/model-results-integrity` into `main` (it also carries v0.4).
4. Whether to keep the 99,118,347-byte `results/tables/evaluation_summary.json` in git.
