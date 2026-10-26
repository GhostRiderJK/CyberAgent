# AGENTS.md — CyberAgent project guide for AI coding assistants

Read this file fully before making any change. It is the source of truth about what this project is, how it is laid out, and the rules for working in it. If something here contradicts what you see in the repo, trust the repo, then tell the user and propose an edit to this file.

## 1. What this project is

**CyberAgent: Agent-Assisted Network Threat Detection and Investigation using Machine Learning.**

An ML classifier detects and classifies malicious network flows (CIC-IDS2017). An AI investigation agent then examines suspicious flows with tools and produces an evidence-based threat assessment. A grounding verifier checks the agent's narrative against tool evidence.

- Academic use: AUCML (TE7483, Sem 5) ESE case-study project, graded on a 30-mark rubric. Code quality, honesty of results, reproducibility and clear limitations matter.
- The **classifier output is authoritative**. The LLM narrative never overrides the predicted class.
- Owner: Jai (3rd-year BTech AIML student). Solo project.

## 2. Environment rules (important)

- OS: **Windows** (cmd/PowerShell). **`make` is NOT installed.** Never tell the user to run only `make ...`. Always give the underlying command too (for example `uv run python -m scripts.evaluate`, `npm run sync:eval`). The README "Usage" section has the full target-to-command table.
- Project root (as last reported): `D:\Project\security-network\AUCML`. Verify with `pwd` and do not assume.
- Backend: Python, managed with **`uv`** (`uv run ...`). API framework: FastAPI. Tests: `uv run pytest -q`.
- Frontend (`frontend/`): React 19, Vite, Tailwind v4, react-router-dom, TypeScript. Tests: Vitest (`npm test`). Dev server: `npm run dev` on `localhost:5173`.
- There is **no real `.env`** (only `.env.example`). The agent runs on the **mock LLM backend**. Never require secrets or paid API keys for code to run or tests to pass.
- Use path-safe commands for Windows. Be careful with backslashes and with file names containing `D:` — three tracked files at the frontend root had that shape and their colons were really U+F03A, so literal pathspecs could not match them (they were removed in `81c84e9`; see section 9).

## 3. Non-negotiable working rules

1. **Never invent numbers.** Every metric, count, percentage, timing or label shown in the UI or docs must come from a real artifact (`artifacts/eval/evaluation.json`, `models/metrics.json`, logs, or a test run). If it cannot be sourced, show an honest empty state (for example "—" or "not in the record"), never a plausible placeholder.
2. **Inspect before changing.** Read the relevant files first. Report a short summary of findings, then proceed.
3. **Work on a branch**, never directly on `main`. Small, logical commits with clear messages. Tag milestones (`v0.x-name`).
4. **Add or update tests** for every behavior change. Run `uv run pytest -q`, `npm test`, `npx tsc -b`, `npm run lint` and `npm run build` before declaring done, and report the real results.
5. **Do not claim something was verified unless you actually ran it.** State clearly what was verified and what was not.
6. Keep the honesty convention in the UI: amber badges (`badge badge-amber`) for anything that is not live: "Demo data", "Demo fixtures", "Simulated — not live traffic". Do not remove them.
7. Use the shared class-label and formatting modules (see section 6). Do not hardcode class names or format confidence ad hoc. Confidence is shown with two decimals and must never display as "100.00%" unless the value is exactly 1.0.
8. Do not commit generated or binary run state (`mlflow.db`, `frontend/stats.html`, large logs). Do not delete files the user did not name; propose deletions instead.
9. Do not add new UI libraries. Reuse the existing Card/Badge components and CSS tokens.
10. Prefer deterministic, seeded behavior. Same seed must give the same output.

## 4. Data and ML pipeline

- Dataset: **CIC-IDS2017**, reduced for size. Processed: `data/processed/flows_features.parquet` (389,616 rows), `flows_meta.parquet`. Raw CSVs and the huge PCAPs are not used.
- **Supervised label set (11 classes)**, defined as `EXPECTED_SUPERVISED_LABELS` in `src/cyberagent/preprocess.py`:
  BENIGN, Bot, DDoS, DoS GoldenEye, DoS Hulk, DoS Slowhttptest, DoS slowloris, FTP-Patator, PortScan, SSH-Patator, Web Attack.
  "Web Attack Brute Force" and "Infiltration" are **not** model classes (they appeared only in old mock data).
- Split: `split_data()` in `src/cyberagent/preprocess.py`, stratified 70/15/15, `random_state=42`. Test set = **53,342** rows. Split indices are **not persisted**; rebuilding them requires re-running the preprocessing pipeline.
- Zero-day holdout: 47 flows of unseen attack types, held out. Result: all 47 predicted BENIGN. Keep this visible and honest.
- Models (joblib in `models/`): LightGBM (best by macro F1), XGBoost, Logistic Regression, Random Forest, MLP, Isolation Forest. String labels use an internal `label_encoder_` attached in `src/cyberagent/train.py`.
- Tuning is disabled (`tuning.enabled: false` in `config.yaml`); `tuning_results.json` does not exist.
- MLflow local store: `mlruns/`, `mlflow.db`.
- Scripts (run as `uv run python -m scripts.<name>`): `reduce_dataset`, `preprocess`, `train`, `tune`, `evaluate`, `agent_eval`. Also `scripts/build_evaluation_json.py` (`uv run python scripts/build_evaluation_json.py`), plus `scripts/poc.py` (end-to-end proof of concept for detector + agent tool calling) and `scripts/tasks.py` (a cross-platform Python task runner that mirrors the Makefile targets — useful because `make` is absent), and the shell wrappers `scripts/run_pipeline.sh`, `scripts/run_eval_chain.sh`.
- Evaluation artifacts:
  - `models/metrics.json`, `models/best_model_info.json`
  - `results/tables/model_comparison.csv|md`, `per_class_metrics_*.csv`, `zero_day_holdout_results.csv|md`
  - `results/tables/evaluation_summary.json` (99 MB on disk; 11x11 confusion matrices, per-class PR/ROC arrays)
  - **`artifacts/eval/evaluation.json`**: the single, self-checking source of truth for the frontend (confusion matrix diagonal / total must equal reported accuracy). Synced to the frontend with `npm run sync:eval`.
- Known real numbers: LightGBM accuracy about 99.89% (53,283 / 53,342). Real LightGBM inference about 29.83 ms per 1000 samples. Always read exact values from `evaluation.json`, do not copy them from this file.
- Not persisted: per-sample predicted probabilities, SHAP outputs on disk (SHAP is computed at investigation time), split indices. Training time only exists as log lines in `pipeline_run.log`; if unavailable, show "—".

## 5. Backend and agent

- API: `src/cyberagent/api/main.py`. Routes: `GET /health`, `GET /model/status`, `POST /predict` (flow_id), `GET /flow/{flow_id}`, `/investigate` (SSE), `/`. No route serves evaluation files (the frontend reads the synced `evaluation.json`). Models (Pydantic) in `src/cyberagent/api/models.py`.
- Investigation tools: `src/cyberagent/investigation.py`. Agent: `src/cyberagent/agent/investigation_agent.py` (`AVAILABLE_TOOLS` around line 28). Grounding verifier: `src/cyberagent/agent/grounding.py`.
- Tools: `predict_proba`, `explain_flow`, `find_related_flows`, `similar_known_attacks`, `lookup_attack_pattern`.
- `explain_flow` returns `flow_id`, `predicted_class`, `confidence`, `shap_values[]`, `feature_names[]`, `feature_values[]` (parallel arrays, top 10 by |SHAP|), `value_scale` (always `"standardized"` — the served rows are post-scaler z-scores, not packet counts) and `explanation_error`. Never flatten this into prose and then try to parse it (that was the past bug where the SHAP panel read "No explanation data" under a verdict quoting SHAP values).
- What the UI actually receives: the agent re-shapes the tool result into `shap_explanation` = `{predicted_class, value_scale, features: [{feature, shap_value, standardized_value}], explanation_error}`, alongside `flow_record`, `needs_human_review_reason` and `tool_call_events` on the investigation result (`src/cyberagent/agent/investigation_agent.py`, `_shap_explanation`). `frontend/src/lib/investigation.ts` parses that defensively.
- "Needs Human Review" is set by a deliberate policy (high-impact classes such as Web Attack always need review). The reason is returned as `needs_human_review_reason` and must be displayed; `_determine_needs_human_review` is covered by `tests/test_review_policy.py`.
- The grounding verifier runs five checks, including `identifiers_grounded`: any IPv4 literal quoted in the narrative must appear in the tool evidence or the stored flow record. Failed checks are listed individually in `grounding_check`.
- MITRE mapping is a simplified heuristic (for example Web Attack to T1190). Say so in limitations; do not present it as authoritative.
- The investigation stops after a bounded number of tool calls (`MAX_TOOL_CALLS = 6`) and uses the predefined tool set above. These are listed as limitations.
- Tests: `tests/` (15 `test_*.py` files plus `conftest.py`; 110 passing at last report). Run with `uv run pytest -q`. Never run the suite alongside a pipeline or API process on this machine — torch contention segfaults; and `import magic` hangs unless `libmagic.dll` + `magic.mgc` sit in the run directory.

## 6. Frontend

Location: `frontend/`. Stack: React 19, Vite, Tailwind v4, TypeScript, react-router-dom (routes in `App.tsx`, nav in `Sidebar`, `TopBar` shows API status).

Routes:
- `/` Security Overview (fixture-backed; best macro F1 and backend health come from real sources)
- `/alerts` Network flow alerts (demo fixtures, plus optional "Simulated" rows from the simulation bridge)
- `/investigation` Investigation report (verdict, SHAP bars, tool timeline, flow record, evidence table, recommended actions, limitations)
- `/model-results` Model comparison, confusion matrix (counts and row-normalized), stepped PR curves; **rendered only from `evaluation.json`**
- `/replay` Flow replay (static fixtures, "Demo fixtures" badge)
- `/simulation` Attack/defense simulation

Shared modules (use them, do not duplicate):
- `frontend/src/lib/classLabels.ts` — single class list, display aliases, `flowIdLabel`, and `NOT_IN_MODEL_LABEL_SET` marking for labels the model cannot emit
- `frontend/src/lib/format.ts` — formatting helpers (confidence two decimals, integers, durations)
- `frontend/src/lib/investigation.ts` — parsing of the investigation response (defensive)
- `frontend/src/components/shared/ClassLabel.tsx`
- `frontend/src/models/evaluation.ts` — typed, defensive loader for `evaluation.json`
- `frontend/src/services/useApiHealth.ts` — real `GET /health` status used by TopBar and the Overview health card
- Sync script: `frontend/scripts/sync-eval.mjs` (`npm run sync:eval`, also runs in `prebuild`)
- UI primitives: shadcn-style `Card` and `Badge` in `components/ui/`, CSS tokens in `index.css` (`.glass`, `.surface`, `.panel`, `.eyebrow`, `.badge`, `.badge-amber`, navy palette, `font-display`).

Note: a `.gitignore` rule for `lib/` once silently hid `frontend/src/lib/`; `!frontend/src/lib/` and `!frontend/src/lib/**` re-include it. Do not reintroduce a broad `lib/` ignore.

## 7. Simulation feature (v0.4)

Frontend-only, deterministic, rule-based. NOT a learned RL agent and NOT real traffic. Always labeled "Simulated — not live traffic".

- Engine (pure TS, no React) in `frontend/src/simulation/`: `types`, `rng` (seeded mulberry32), `topology`, `agents`, `engine`, `swarm`, `recommendations`. Tests: `engine.test.ts` (9 passing at last report).
- UI: `Simulation.tsx`, `WarGameReplay.tsx`, `WhatIfPanel.tsx`; alerts bridge in `demoAlerts.ts`, `demoAlertsStore.ts`.
- Network: DMZ (web-server-01 10.0.0.10, mail-server-01 10.0.0.20), INTERNAL (workstation-01 10.0.1.10, file-server-01 10.0.1.20), CRITICAL (prod-db-01 10.0.2.10, dc-01 10.0.2.20). CVEs: CVE-2024-7347 (web-server-01), CVE-2024-38077 (workstation-01), CVE-2024-10978 (prod-db-01). List each CVE once per host.
- Attackers: opportunist, apt, ransomware, insider. Defenders: soc_analyst, incident_responder, threat_hunter. `do_nothing` must stay rare (under 10%). "Success" must mean the action achieved its effect; success, compromise and detection rates must be mutually consistent.
- Replay state is always derived from the step log (`foldSteps(hosts, steps.slice(0, i))`), so scrubbing is consistent. Keyboard: space = play/pause, arrows = step. Respect `prefers-reduced-motion`.
- What-if re-runs with the same seed so differences come only from the toggled defenses.
- Swarm mode reports convergence honestly (including "not converged").
- Known tuning point: detection rate is low (about 6% in the seed-42 demo run). Raising detection when EDR is on is a reasonable future change.

## 8. Git state and history

- Branches: `feature/simulation` (tag `v0.4-simulation`), `fix/model-results-integrity` (tag `v0.5-integrity`, cut from `feature/simulation`, so it contains both). Merge target: `main` (still open — the owner chose to review before merging).
- Earlier tags: `v0.1-poc`, `v0.2-prototype`, `v0.3-mvp`.
- Integrity work (v0.5), oldest first: `b659587` self-checking `evaluation.json` generator, `db1bd62` sync + defensive loader, `965a6da` shared class labels and formatting, `6f0cb43` Model Results rebuilt from the artifact, `fc75e24` flow IDs / class names / backend status agree across pages, `77a561a` backend returns structured SHAP, flow identifiers and the review reason, `8a80565` investigation page shows only what the backend returned, `feec7bc` README evaluation section, `81c84e9` frontend-root junk files removed (lint clean), `d1aec49` shadowed `description` keys removed.
- `8a80565` replaced the earlier `8c221a6`, whose message wrongly claimed a mock investigation file remained untracked; the branch was never pushed, so the message was corrected by rewriting the last two commits.

## 9. Open items (update this list as they are done)

- [x] Delete the 4 tracked junk files at the frontend root that broke `npm run lint` (`orig_investigation.tsx` and three `D...suitable-*.tsx`). Done in `81c84e9`; lint is now 0 warnings / 0 errors on 51 files.
- [x] Amend the `8c221a6` commit message. Done as part of the rewrite; the commit is now `8a80565`.
- [x] Remove the duplicate `description` keys in `src/cyberagent/investigation.py` (the earlier key in each fallback dict was silently overwritten). Done in `d1aec49`; returned strings unchanged, 110 tests still pass.
- [x] README and Makefile mention `make` targets; add plain-command equivalents because `make` is not installed. Done — see the target table at the top of README "Usage".
- [ ] Merge `fix/model-results-integrity` into `main` (it also carries the v0.4 simulation work).
- [ ] Consider code-splitting Model Results (bundle about 951 kB, mostly the inlined 192 kB `evaluation.json`) if deploying to Vercel.
- [ ] Optional: a split-by-day evaluation to test leakage from the random split.
- [ ] Optional companion metric for the zero-day holdout (Isolation Forest anomaly score alongside the supervised prediction) — awaiting the owner's decision.
- Uncommitted on purpose, do not commit: `mlflow.db` and `frontend/stats.html` (generated/binary run state, modified by the verification runs), `pipeline_run.log` and `eval_chain.log` (the derivation record for the reported metrics).

## 10. Known limitations (keep honest in docs and UI)

1. Random stratified split may leak near-duplicate flows between train and test, so scores may be optimistic.
2. Zero-day holdout failed: all 47 unseen flows were classified BENIGN.
3. PR curves exist for the best model only.
4. The agent runs on a mock LLM backend without a real `.env`; do not make LLM-quality claims.
5. MITRE mapping is heuristic; the agent has a bounded tool set and tool-call budget.
6. Simulation is rule-based and illustrative.
7. Overview, Alerts and Replay pages use labeled fixtures, not live traffic.
8. Per-sample probabilities and split indices are not persisted, so a single flow's supervised prediction cannot be re-derived from disk alone; the investigation path recomputes it from the loaded model.

## 11. How to respond to the user

- Be concise. State what you changed, what you verified (with real command results), and what you skipped and why.
- When you find an inconsistency or risky result, say so plainly instead of smoothing it over.
- When asked for a plan or prompt, make it complete and ready to use, with Windows-safe commands.
- If this file is out of date after your work, update the relevant section in the same branch.
