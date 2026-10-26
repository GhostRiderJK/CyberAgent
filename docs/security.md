# Security notes — CyberAgent

Written for a research artifact that runs on a laptop against a public dataset. It is not a product
security review, and nothing here has been penetration-tested.

## Trust boundaries

| Input | Who controls it | How the code treats it |
| --- | --- | --- |
| Flow feature values | the sender of the traffic | model input only; never echoed as text |
| Stored flow metadata (`flows_meta.parquet`) | the reduction script, over a public capture | `get_flow_record` coerces ports and protocol to `int`, returns `null` plus `missing_fields` for absent columns |
| LLM output | the remote model | prose fields only; checked by the grounding verifier |
| `*.joblib` model and artifact files | whoever writes them to disk | loaded with `joblib.load`, i.e. pickle |
| Frontend | the build | reads the inlined `evaluation.json` snapshot; no route serves metrics |

## Prompt-injection surface as it stands

`_select_next_tool` (`src/cyberagent/agent/investigation_agent.py:81`) sends the model only `flow_id`,
`predicted_class`, `confidence`, the tools already called and the calls remaining (`:91-95`) - no
traffic content. The reply is rejected unless the tool name is in `AVAILABLE_TOOLS`, is not
`predict_proba` and has not run (`:104`). Arguments then pass `_normalize_args` (`:63`), which
overwrites `flow_id` and `label` with trusted values, pins `time_window_minutes=30` (`:71`) and `k=5`
(`:73`) and drops keys outside the tool signature, and the loop stops at `MAX_TOOL_CALLS = 6` (`:25`).

`_narrative_from_llm` (`:208`) is the wider channel: it serialises compacted tool evidence truncated to
6000 characters (`:223`). The strings inside that payload are feature names, class labels, the static
MITRE table and exception text - there is no free-text field from the capture in it today. Add one
(HTTP URI, SNI, DNS name, payload bytes) and indirect injection becomes reachable, with the grounding
checks as the only thing between that output and the report.

A manipulated narrative still cannot change the label: `ml_label_not_overridden` fails the run when
prose disagrees with `predicted_class`, and any failed check routes the report to human review.

## What the verifier does not prove

The five checks in `src/cyberagent/agent/grounding.py` (`:77`, `:82`, `:108`, `:115`, `:126`) compare
strings and numbers in the narrative against the evidence. They do not confirm the evidence itself is
truthful, do not detect omission or hedging, and do not judge whether a correctly quoted number is
used to support a wrong conclusion. `tests/test_grounding.py` covers 8 cases of the checks that do
exist; nothing tests what they miss.

## Secrets

`src/cyberagent/llm.py` reads configuration from the environment only: `_env` wraps `os.environ.get`
(`:26-27`), `load_dotenv()` is attempted (`:39-40`), the names are `LLM_BACKEND`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_S` (`:44-50`), and the
key becomes a bearer header (`:91-92`). Default backend is `mock`, so the project runs with no key at
all. `.gitignore` ignores `.env` (`:53`) and `.env*` (`:92`); the tracked `.env.example` puts
`your_omnirouter_key_here` where a key would go. The history scan over all 55 commits found no key,
token or `.env` contents. Never paste a key into a doc, commit message or log line, and do not print
`.env`.

## API exposure today

- `config.yaml:80-84` sets `api.host: "0.0.0.0"` and port 8000, and `api/__main__.py:6-8` passes both
  to uvicorn, so `uv run python -m cyberagent.api` listens on every interface. `start.bat:12` instead
  runs `uvicorn cyberagent.api.main:app --host 127.0.0.1 --port 8010`.
- No authentication or rate limiting exists: `Depends(` appears nowhere in `api/main.py` and there is
  no key check on the six routes (`:72`, `:77`, `:109`, `:127`, `:140`, `:187`). Any flow record can be
  read by `flow_id`, and `/investigate` runs model work for any caller.
- CORS (`:39-43`) pins origins to `api.cors_origins` but sets `allow_credentials=True` with
  `allow_methods=["*"]` and `allow_headers=["*"]`.
- Error text leaks internals on the paths that matter most: `/predict` returns 404 with `str(e)`
  (`:121`), `/flow/{id}` returns the stored reason (`:132`) which can carry an exception message
  (`investigation.py:179`), and `/investigate` emits `{'error': str(e)}` over SSE (`:181-182`). The 500
  responses are generic `Internal server error` (`:106`, `:124`).
- `/investigate` takes a worker from `ThreadPoolExecutor(max_workers=4)` (`:28`) with no queue limit, so
  four concurrent investigations occupy the pool and the fifth waits.
- Model files are pickle. `joblib.load` runs at `investigation.py:75` and `:85`, `explain.py:201`,
  `anomaly.py:135` and `:141`, `scripts/evaluate.py:128` and `:150`; loading a `*.joblib` from an
  untrusted source executes code. `models/*.joblib` and `data/processed` are gitignored
  (`.gitignore:75-76`), so whoever distributes them is the only trust anchor.

## Detection limits that are security-relevant

- The 47-flow zero-day holdout (Heartbleed, Infiltration) scores macro F1 0.0000 for all five
  supervised models (`eval_chain.log:168-252`, `results/tables/zero_day_holdout_results.csv`): an
  unseen technique is not detected.
- The stratified random split can put near-duplicate flows on both sides, so the reported accuracy is
  plausibly optimistic; a split-by-day evaluation has not been run.
- No adversarial or evasion test exists. Feature-space behaviour under deliberate shaping is
  unmeasured, not assumed good.
- MITRE mapping is a fixed lookup keyed on the predicted class, not a threat-intelligence feed.
- `/simulation` is seeded rule-based theatre and proves nothing about detection.

## Before pointing this at anything real

1. Bind loopback or a private interface, terminate TLS at a reverse proxy, and put authentication there.
2. Add per-principal authorization to all six routes; today any `flow_id` is readable by anyone.
3. Set `allow_credentials=False` or list only origins that genuinely need cookies.
4. Replace `str(e)` in `/predict`, `/flow/{id}` and the SSE error event with an opaque id logged
   server-side.
5. Give `/investigate` a queue limit and a timeout instead of an unbounded threadpool hand-off.
6. Keep `_normalize_args` and the `AVAILABLE_TOOLS` membership test; treat every new string that enters
   `_narrative_from_llm` as attacker-controlled and add it to the grounding evidence set.
7. Store `*.joblib` read-only with a recorded checksum and never load one from a third party.
8. Rotate any key that has ever been pasted, and keep `.env` out of the repo and out of logs.
9. Run request-level API tests first - none exist (`docs/testing.md`), so none of the above is verified
   by the suite.

## Not tested

No penetration test, no fuzzing of the SSE endpoint, no dependency audit has been run against
`uv.lock` (1,640 `sha256:` hashes) or `frontend/package-lock.json` (210 `integrity` fields), no TLS
or proxy configuration exists in this repo, and no adversarial examples have been generated.
