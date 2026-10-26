# AGENTS.md — CyberAgent, notes for AI coding assistants

Read this before changing anything. Long-form detail lives in `docs/` (Further reading, at the
end). If a line here contradicts the repo, trust the repo, tell the user, propose a fix.

## What this is

CyberAgent: agent-assisted network threat detection and investigation. A LightGBM-led classifier
labels malicious flows from CIC-IDS2017; an investigation agent then examines a flagged flow with
five fixed tools and writes an assessment that a grounding verifier audits against the evidence.
Academic ESE case study (AUCML TE7483, Sem 5, 30-mark rubric). Solo project, owner: Jai.

**The classifier output is authoritative.** The LLM narrative never overrides the predicted class;
that is why `ml_label_not_overridden` is a grounding check.

## Environment

- Windows, cmd/PowerShell. **`make` is not installed.** Never tell the user to run only `make ...`;
  give the underlying command. README "Usage" has the target-to-command table and
  `scripts/tasks.py` mirrors the Makefile targets in Python.
- Backend: Python 3.13 through **`uv`** (`uv run python -m scripts.<name>`, `uv run pytest -q`),
  FastAPI + uvicorn. Frontend: `npm` in `frontend/` (React 19, Vite 8, Tailwind v4, TypeScript).
- A real `.env` **does** exist on the owner's machine (701 bytes, ignored by the `.env*` rule); it
  sets `LLM_BACKEND=openai`, a local base URL, a model id and a 35-character `LLM_API_KEY`.
  `.env.example` keeps the placeholder. No credential is anywhere in git history. Never print the
  key, never commit it. Tests never construct `LLMClient`, so the suite stays offline and mock is
  the default (`src/cyberagent/llm.py:44`) — but with `.env` live and the proxy up, `/investigate`
  really calls the model. Nothing may require a secret to run or to pass.
- Repo root as last reported: `D:\Project\security-network\AUCML`. Verify with `pwd`.

## Working rules

1. Never invent a number. Every metric, count, timing or label in the UI or docs must come from an
   artifact (`artifacts/eval/evaluation.json`, `models/metrics.json`, `results/tables/`, a log, or
   a run you executed). Otherwise show an honest empty state: `—` or "not in the record".
2. Inspect before changing; report what you found, then proceed.
3. Work on a branch, never on `main`. Small logical commits. Tag milestones (`v0.x-name`).
4. Add or update a test for every behavior change, then run and report the real results of
   `uv run pytest -q`, `npm test`, `npx tsc -b`, `npm run lint`, `npm run build`. Latest run:
   110 Python tests pass, 31 frontend tests pass, oxlint 0 warnings / 0 errors on 51 files,
   `tsc -b` exits 0, build succeeds. Gaps: `docs/testing.md`.
5. Never claim something was verified unless you ran it; say what you skipped and why.
6. Keep the amber badges (`badge badge-amber`) that mark non-live content: "Demo data",
   "Demo fixtures", "Simulated — not live traffic". Do not reuse them for real results.
7. Use the shared label and format modules; do not hardcode class names or format confidence ad
   hoc. `formatConfidencePct` caps any value below 1 so it can never read `100.00%`.
8. Do not commit generated or binary run state (`mlflow.db`, `frontend/stats.html`, large logs).
   Never delete a file the user did not name; propose it.
9. No new UI libraries. Reuse `Card`, `Badge` and the tokens in `frontend/src/index.css`.
10. Prefer deterministic, seeded behavior: same seed, same output.

## Data and models

- CIC-IDS2017, reduced copy. `data/processed/flows_features.parquet` = 389,616 rows;
  `flows_meta.parquet` matches it. Raw CSVs and PCAPs are not in the repo.
- 11 supervised classes in `EXPECTED_SUPERVISED_LABELS` (`src/cyberagent/preprocess.py:511`):
  BENIGN, Bot, DDoS, DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, FTP-Patator,
  PortScan, SSH-Patator, Web Attack. "Web Attack Brute Force" and "Infiltration" are not classes.
- `split_data()`, same file: stratified 70/15/15, `random_state=42`. Test split = 53,342 rows.
  Split indices are not persisted, so rebuilding them needs the pipeline.
- LightGBM, selected by macro F1: accuracy 0.998894 (53,283 of 53,342), macro F1 0.995273,
  29.826 ms inference per 1000 samples, 11.28 s training. `artifacts/eval/evaluation.json` is the
  source of truth; this file is a summary.
- Zero-day holdout: 47 unseen-class flows (Heartbleed, Infiltration) in
  `data/processed/holdout_zero_day.parquet`. All 47 were predicted BENIGN — the artifact records
  accuracy 0.0 for all five supervised models. Keep that visible.
- `models/` holds five supervised joblib files plus `isolation_forest{,_scaler}.joblib`,
  `metrics.json` and `best_model_info.json`. **`models/*.joblib`, `data/processed/` and
  `data/raw/` are gitignored**: a fresh clone has the metric artifacts but no models and no
  features, so `/predict` needs the pipeline run first. String labels decode through the
  `label_encoder_` attached in `src/cyberagent/train.py`.
- Tuning is off (`tuning.enabled: false`) and `tuning_results.json` does not exist.
- Scripts, as `uv run python -m scripts.<name>`: `reduce_dataset`, `preprocess`, `train`, `tune`,
  `evaluate`, `agent_eval`; also `uv run python scripts/build_evaluation_json.py`, `scripts/poc.py`,
  `scripts/tasks.py`, `scripts/run_pipeline.sh`, `scripts/run_eval_chain.sh`.

## Backend and agent

- `src/cyberagent/api/main.py`: `GET /health`, `GET /model/status`, `POST /predict` (accepts only a
  `flow_id`), `GET /flow/{flow_id}`, `POST /investigate` (SSE: `start`, `progress`, `end`, `error`),
  `GET /`. No route serves evaluation files; the frontend reads the synced artifact.
- Tools (`AVAILABLE_TOOLS`, `src/cyberagent/agent/investigation_agent.py:28`; implementations in
  `src/cyberagent/investigation.py`): `predict_proba`, `explain_flow`, `find_related_flows`,
  `similar_known_attacks`, `lookup_attack_pattern`. `MAX_TOOL_CALLS = 6` is a module constant.
  `config.yaml` keys `agent.max_tool_calls` and `agent.llm_backend` are **read by no code**.
- With no LLM backend the agent runs a deterministic fallback plan instead of LLM planning. Do not
  describe mock runs as LLM behavior; live-LLM quality is unbenchmarked.
- `explain_flow` returns parallel arrays (`shap_values[]`, `feature_names[]`, `feature_values[]`,
  top 10 by |SHAP|), `value_scale` always `"standardized"` — served rows are post-scaler z-scores,
  not packet counts — and `explanation_error`. The agent reshapes that into `shap_explanation`
  beside `flow_record`, `needs_human_review_reason` and `tool_call_events`; `src/lib/investigation.ts`
  parses it defensively. Never parse prose to recover data: the SHAP panel broke exactly that way,
  reading "No explanation data" under a verdict that quoted SHAP numbers.
- "Needs Human Review" comes from the policy in `_determine_needs_human_review` (high-impact
  classes such as Web Attack always need review); display `needs_human_review_reason`.
  `tests/test_review_policy.py` covers it.
- Grounding (`src/cyberagent/agent/grounding.py`) runs five checks: `ml_label_not_overridden`,
  `confidence_grounded` (±0.05), `numbers_grounded`, `tool_references_valid`,
  `identifiers_grounded` (every IPv4 literal in the narrative must appear in tool evidence or the
  stored flow record). Failures are listed per check.
- MITRE mapping is a heuristic (Web Attack to T1190, for example). Say so; do not present it as
  authoritative.

## Frontend

`frontend/`, routes in `src/App.tsx`: `/` Overview, `/alerts`, `/investigation`, `/model-results`,
`/simulation`, `/replay`, plus a catch-all redirect to `/`. Nav in `components/shared/Sidebar`;
`TopBar` shows real `GET /health` status via `src/services/useApiHealth.ts`. `/model-results`
renders only from the synced artifact.

Truth chain: `scripts/build_evaluation_json.py` re-derives every metric from the confusion matrix
and refuses to write when diagonal/total, macro F1 or weighted scores disagree (accuracy tolerance
1e-6) → `artifacts/eval/evaluation.json` → `npm run sync:eval` (also in `prebuild`) →
`frontend/src/data/evaluation.json` → `src/models/evaluation.ts` → pages. A missing artifact
becomes an explicit "unavailable" record carrying the regeneration command, never a placeholder.

Shared modules — use them, do not duplicate: `src/lib/classLabels.ts` (the 11 classes, alias map,
`NOT_IN_MODEL_LABEL_SET`, `classColor`, `flowIdLabel` → `FLOW-0042`), `src/lib/format.ts`,
`src/lib/investigation.ts` (defensive parse), `src/components/shared/ClassLabel.tsx`,
`src/models/evaluation.ts`, `components/ui/{card,badge,table}.tsx`, and the CSS classes in
`src/index.css` (`.glass .surface .panel .eyebrow .badge .badge-amber .mono .font-display`).

A `.gitignore` rule for `lib/` once silently hid `frontend/src/lib/`; the two `!frontend/src/lib`
re-include lines fix it. Do not reintroduce a broad `lib/` ignore.

## Simulation (`/simulation`, since v0.4)

Frontend-only, deterministic, rule-based. Not a learned agent, not real traffic, always labeled
"Simulated — not live traffic". Engine (pure TS, no React) in `src/simulation/`: `types`, `rng`
(seeded mulberry32), `topology`, `agents`, `engine`, `swarm`, `recommendations`; UI in
`pages/Simulation.tsx` and `components/simulation/{WarGameReplay,WhatIfPanel}.tsx`; alerts bridge
in `state/{demoAlerts,demoAlertsStore}.ts`.

Hard constraints: replay state always derives from the step log
(`foldSteps(hosts, steps.slice(0, i))`, `WarGameReplay.tsx:70`) so scrubbing stays consistent;
space = play/pause, arrows = step; respect `prefers-reduced-motion`; what-if re-runs reuse the
seed so only the toggled defense differs; swarm reports non-convergence honestly; `do_nothing`
stays under 10%; "success" means the action achieved its effect and success, compromise and
detection rates must agree with each other; each CVE appears once per host. At the page defaults
(timesteps 5, seed 42) detection is 2 of 35 actions — the weak number, worth tuning when EDR is on.

## Git

Branches: `main`, `feature/simulation`, `fix/model-results-integrity` (cut from `feature/simulation`,
so it carries v0.4 and v0.5), `chore/cleanup`, `phase/1-ideation` … `phase/4a-real-run`. Tags:
`v0.1-poc`, `v0.2-prototype`, `v0.3-mvp`, `v0.4-simulation`, `v0.5-integrity`. Merge target is
`main`, and the owner reviews before merging. No force-push, no push without asking. Refer to work
by tag or commit subject, never by hash: the message history was rewritten and old hashes are gone.

Deliberately uncommitted — do not commit: `mlflow.db`, `frontend/stats.html` (both already sit in
history from a pre-cleanup commit), `pipeline_run.log` and `eval_chain.log` (the derivation record
behind the reported metrics).

## Open items

- [ ] Merge `fix/model-results-integrity` into `main` (it carries v0.4 and v0.5).
- [ ] Decide whether the tracked 99,118,347-byte `results/tables/evaluation_summary.json` belongs
      in git; it dominates the repo.
- [ ] One mangled file is still tracked at the frontend root: `git ls-files` prints it as
      `"frontend/D\357\200\272ProjectAUCMLfrontendsrcmodelsapiModels.ts"` (the colon is U+F03A, so
      a literal pathspec will not match). One line, stale copy of `src/models/apiModels.ts`,
      unreferenced. Propose deletion; do not delete unilaterally.
- [ ] `frontend/tailwind.config.js` (+ `.backup`) is dead config: Tailwind v4 loads through
      `@tailwindcss/vite` with no `@config` directive, so its `navy` palette never reaches the
      build while `components/ui/badge.tsx` and `table.tsx` still emit `bg-navy-*` classes.
- [ ] Code-split `/model-results` before deploying: single chunk measured 951.58 kB (gzip
      235.06 kB), mostly the inlined 196,309-byte artifact copy.
- [ ] Optional: split-by-day evaluation to test leakage from the random split.
- [ ] Optional: Isolation Forest score next to the supervised prediction for the zero-day holdout
      — awaiting the owner's decision.

## Known limitations (keep them honest in docs and UI)

1. A random stratified split can leak near-duplicate flows into test, so scores may be optimistic.
2. Zero-day holdout failed: all 47 unseen flows were classified BENIGN.
3. PR curves exist for the best model only (one-vs-rest, capped at 200 points per class).
4. Default runs use the mock backend and its deterministic plan; live-LLM behaviour is unbenchmarked.
5. MITRE mapping is heuristic; the tool set and tool-call budget are bounded.
6. Simulation is rule-based and illustrative.
7. Overview, Alerts and Replay are labeled fixtures, not live traffic.
8. Per-sample probabilities and split indices are not persisted; the investigation path recomputes
   a flow's prediction from the loaded model. Training time is real and lives in
   `evaluation.json` as `models[*].training_time_s` (LightGBM 11.28 s); the table falls back to `—`
   only when every model reports it as null.

## Further reading

- `docs/prd.md` — problem, users, requirements with real status, open decisions.
- `docs/architecture.md` — offline pipeline, online request path, module ownership, decisions and why.
- `docs/design_system.md` — tokens, badge rules, formatting, known inconsistencies.
- `docs/testing.md` — what is covered, fresh counts, what has no automated coverage.
- `docs/security.md` — trust boundaries, pickle and API exposure notes, pre-exposure checklist.
