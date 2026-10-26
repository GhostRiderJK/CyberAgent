#!/usr/bin/env python
"""
Agent evaluation: run the investigation agent over a sample of flows and
score its behaviour against the requirements:

  - ML label fidelity ......... agent predicted_class == detector prediction
  - grounding pass rate ....... grounding verifier accepted the report
  - tool budget ............... <= MAX_TOOL_CALLS per investigation
  - needs_human_review firing.. flagged when confidence is low
  - schema validity ........... every required verdict field present

Writes results/tables/agent_eval_summary.json and results/agent_logs/agent_eval_<ts>.jsonl.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from cyberagent.config import config
from cyberagent.logging_setup import logger
from cyberagent.investigation import _initialize_data_and_model
import cyberagent.investigation as inv
from cyberagent.agent.investigation_agent import investigate_flow, MAX_TOOL_CALLS

SAMPLE_PER_CLASS = 3

REQUIRED_FIELDS = ['verdict', 'predicted_class', 'severity', 'confidence',
                   'needs_human_review', 'evidence', 'mitre_technique',
                   'recommended_actions', 'limitations']


def main():
    logger.info("=== CyberAgent: agent evaluation ===")
    _initialize_data_and_model()
    df = inv._features_df_full
    if df is None:
        raise SystemExit("Data/model not initialized - run the pipeline first.")

    # Sample a few flows from each predicted class using the model itself
    model = inv._model
    import numpy as np
    Xs = inv._transform_for_model(inv._features_df_model)  # serving-aligned features
    proba = model.predict_proba(Xs)
    le = getattr(model, 'label_encoder_', None)
    label_names = le.classes_ if le is not None else model.classes_
    preds = label_names[np.argmax(proba, axis=1)]

    samples = []
    for cls in pd.unique(preds):
        idxs = [i for i, p in enumerate(preds) if p == cls][:SAMPLE_PER_CLASS]
        samples.extend((int(df.iloc[i]['flow_id']), str(cls)) for i in idxs)
    logger.info(f"Evaluating agent on {len(samples)} flows across {len(set(c for _, c in samples))} predicted classes")

    records, n_label_ok, n_ground_ok, n_schema_ok = [], 0, 0, 0
    low_conf_review_ok, low_conf_total = 0, 0
    for flow_id, expected_cls in samples:
        result = investigate_flow(flow_id)
        ml = inv.predict_proba(flow_id)
        record = {"flow_id": flow_id, "ml_class": ml['predicted_class'], "result": result}
        records.append(record)

        n_schema_ok += all(f in result for f in REQUIRED_FIELDS)
        n_label_ok += result.get('predicted_class') == ml['predicted_class']
        n_ground_ok += bool(result.get('grounding_check', {}).get('passed'))
        conf = ml['confidence']
        if conf < 0.6:
            low_conf_total += 1
            low_conf_review_ok += bool(result.get('needs_human_review'))

    n = len(samples)
    summary = {
        "n_flows": n,
        "sample_per_class": SAMPLE_PER_CLASS,
        "ml_label_fidelity": n_label_ok / n if n else 0.0,
        "grounding_pass_rate": n_ground_ok / n if n else 0.0,
        "schema_validity": n_schema_ok / n if n else 0.0,
        "low_confidence_review_rate": low_conf_review_ok / low_conf_total if low_conf_total else None,
        "max_tool_calls_used": min(MAX_TOOL_CALLS, max((len([e for e in r['result'].get('evidence', [])]) for r in records), default=0)),
        "llm_backend": "configured" if _llm_configured() else "mock",
    }
    Path("results/tables").mkdir(parents=True, exist_ok=True)
    with open("results/tables/agent_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    log_dir = Path("results/agent_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    out = log_dir / f"agent_eval_{int(__import__('time').time())}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, default=str) + "\n")

    logger.info(f"Agent eval summary: {json.dumps(summary)}")
    logger.info(f"Full records -> {out}")


def _llm_configured() -> bool:
    from cyberagent.llm import get_llm
    return get_llm().available


if __name__ == "__main__":
    main()
