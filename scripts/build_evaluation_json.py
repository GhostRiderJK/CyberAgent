#!/usr/bin/env python
"""
Build the single evaluation artifact the frontend is allowed to render from.

Reads the real pipeline outputs and writes ONE file:
  artifacts/eval/evaluation.json

Sources (all produced by the pipeline, nothing invented here):
  models/metrics.json                  -> per-model accuracy / weighted P-R-F1 /
                                          macro F1 / 11x11 confusion matrix /
                                          per-class support, measured inference time
  models/best_model_info.json          -> cross-check of the selected model
  results/tables/evaluation_summary.json -> one-vs-rest precision-recall curves
  pipeline_run.log                     -> training wall-clock (optional; null when absent)

Every number written is re-derived from the confusion matrix and asserted against the
reported value before the file is written (see self_check). If a source artifact is
missing the script says which one, prints the command that regenerates it and stops;
it never substitutes a plausible-looking placeholder.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
BEST_MODEL_PATH = REPO_ROOT / "models" / "best_model_info.json"
SUMMARY_PATH = REPO_ROOT / "results" / "tables" / "evaluation_summary.json"
TRAIN_LOG_PATH = REPO_ROOT / "pipeline_run.log"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "eval" / "evaluation.json"

MAX_PR_POINTS = 200
ACCURACY_TOL = 1e-6

REGEN_COMMANDS = {
    "models/metrics.json": "make train      # -> python scripts/train.py",
    "results/tables/evaluation_summary.json": "make evaluate  # -> python scripts/evaluate.py",
}

REPORT_AGGREGATE_KEYS = {"accuracy", "macro avg", "weighted avg"}


class ArtifactError(RuntimeError):
    """A required source artifact is missing or internally inconsistent."""


def _load_json(path: Path, maker: str) -> Any:
    if not path.exists():
        raise ArtifactError(
            f"Missing required artifact: {maker}\n"
            f"  Regenerate it with: {REGEN_COMMANDS[maker]}\n"
            "  Refusing to write evaluation.json because every number in it must come "
            "from a real measurement."
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _matrix_metrics(matrix: List[List[int]], labels: List[str]) -> Dict[str, Any]:
    """Re-derive headline metrics from a confusion matrix (rows=true, cols=predicted)."""
    rows = [sum(r) for r in matrix]
    cols = [sum(matrix[i][c] for i in range(len(labels))) for c in range(len(labels))]
    diag = [matrix[i][i] for i in range(len(labels))]
    total = sum(rows)
    tp = sum(diag)
    per_class = {}
    w_p = w_r = w_f = 0.0
    for i, label in enumerate(labels):
        support = rows[i]
        precision = (diag[i] / cols[i]) if cols[i] else 0.0
        recall = (diag[i] / support) if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": int(support),
        }
        if total:
            w_p += precision * support / total
            w_r += recall * support / total
            w_f += f1 * support / total
    macro_f1 = sum(per_class[l]["f1"] for l in labels) / len(labels) if labels else 0.0
    return {
        "accuracy": (tp / total) if total else 0.0,
        "precision_weighted": w_p,
        "recall_weighted": w_r,
        "f1_weighted": w_f,
        "f1_macro": macro_f1,
        "per_class": per_class,
        "total": int(total),
        "correct": int(tp),
    }


def _labels_from_report(report: Dict[str, Any], matrix: List[List[int]]) -> List[str]:
    """The matrix axis order is the classification-report order (sklearn sorts labels)."""
    labels = [k for k in report.keys() if k not in REPORT_AGGREGATE_KEYS]
    if len(labels) != len(matrix) or any(len(row) != len(labels) for row in matrix):
        raise ArtifactError(
            f"Confusion matrix shape {len(matrix)}x{len(matrix[0]) if matrix else 0} does not "
            f"match the {len(labels)} classes in the classification report: {labels}"
        )
    return labels


def _self_check(model_name: str, metrics: Dict[str, Any], derived: Dict[str, Any],
                reported_accuracy: float, reported_macro_f1: float, n_samples: int) -> None:
    failures: List[str] = []
    if derived["total"] != n_samples:
        failures.append(
            f"confusion matrix sums to {derived['total']}, n_samples is {n_samples}"
        )
    if abs(derived["accuracy"] - reported_accuracy) > ACCURACY_TOL:
        failures.append(
            f"matrix diagonal/total = {derived['accuracy']:.8f} but reported accuracy = "
            f"{reported_accuracy:.8f} (tolerance {ACCURACY_TOL:g})"
        )
    if abs(derived["f1_macro"] - reported_macro_f1) > 5e-4:
        failures.append(
            f"matrix-derived macro F1 = {derived['f1_macro']:.6f} but reported macro F1 = "
            f"{reported_macro_f1:.6f}"
        )
    for key, reported_key in (("precision_weighted", "precision"), ("recall_weighted", "recall"),
                              ("f1_weighted", "f1")):
        reported = metrics.get(reported_key)
        if isinstance(reported, (int, float)) and abs(derived[key] - float(reported)) > 5e-4:
            failures.append(
                f"matrix-derived weighted {reported_key} = {derived[key]:.6f} but reported = "
                f"{float(reported):.6f}"
            )
    if failures:
        raise ArtifactError(
            f"Self-check FAILED for model '{model_name}' - the artifact is internally "
            "inconsistent, so nothing derived from it can be trusted:\n  - "
            + "\n  - ".join(failures)
        )


def _pr_curve_for_model(summary: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    """Downsample the stored one-vs-rest PRC arrays to <= MAX_PR_POINTS points.

    sklearn returns the arrays in descending recall order; we reverse them so the
    frontend can plot x = recall left-to-right. Sampling is by evenly spaced index, so
    every point is a real (precision, recall) pair from the curve - no interpolation,
    no smoothing.
    """
    model_block = summary.get("test_set", {}).get(model_name)
    if not model_block:
        raise ArtifactError(
            f"evaluation_summary.json has no test_set entry for the selected model '{model_name}'."
        )
    prc = model_block.get("prc")
    if not prc:
        raise ArtifactError(
            f"evaluation_summary.json has no precision-recall curves for '{model_name}' "
            "(predict probabilities were unavailable at evaluation time)."
        )
    curves: Dict[str, Any] = {}
    for cls, data in prc.items():
        # sklearn emits descending recall; reverse so the frontend can plot
        # x = recall left-to-right with a step-after line.
        precision = list(reversed(data["precision"]))
        recall = list(reversed(data["recall"]))
        if len(precision) != len(recall) or not precision:
            raise ArtifactError(f"PR curve for class '{cls}' of '{model_name}' is malformed.")
        n = len(precision)
        k = min(n, MAX_PR_POINTS)
        if n == 1 or k == 1:
            idx = [0]
        else:
            idx = sorted({min(n - 1, round(i * (n - 1) / (k - 1))) for i in range(k)})
        points = [{"recall": round(recall[i], 6), "precision": round(precision[i], 6)} for i in idx]
        for p in points:
            if not (0.0 <= p["recall"] <= 1.0 and 0.0 <= p["precision"] <= 1.0):
                raise ArtifactError(
                    f"PR curve for class '{cls}' leaves [0,1]: recall={p['recall']}, "
                    f"precision={p['precision']}"
                )
        if any(points[i]["recall"] < points[i - 1]["recall"] for i in range(1, len(points))):
            raise ArtifactError(f"PR curve for class '{cls}' is not recall-ordered.")
        curves[cls] = {
            "points": points,
            "average_precision": float(data["auc"]),
            "n_thresholds": n,
        }
    return curves


_TRAIN_TIME_RE = re.compile(r"(?P<name>[\w ]+) training time: (?P<secs>[\d.]+)s")
_NAME_TO_MODEL = {
    "Logistic Regression": "logistic_regression",
    "Random Forest": "random_forest",
    "XGBoost": "xgboost",
    "LightGBM": "lightgbm",
    "MLP": "mlp",
}


def _training_times() -> Dict[str, float]:
    """Training wall-clock exists only as log lines; absent means null, never a guess."""
    if not TRAIN_LOG_PATH.exists():
        return {}
    times: Dict[str, float] = {}
    for line in TRAIN_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _TRAIN_TIME_RE.search(line)
        if m:
            key = _NAME_TO_MODEL.get(m.group("name").strip())
            if key:
                times[key] = float(m.group("secs"))
    return times


def _git_commit() -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def build() -> Dict[str, Any]:
    metrics_all = _load_json(METRICS_PATH, "models/metrics.json")
    summary = _load_json(SUMMARY_PATH, "results/tables/evaluation_summary.json")

    n_samples = int(summary.get("n_test_samples") or 0)
    if n_samples <= 0:
        raise ArtifactError("evaluation_summary.json has no usable n_test_samples.")

    models: Dict[str, Any] = {}
    best_candidates: Dict[str, float] = {}
    for name, metrics in metrics_all.items():
        matrix = metrics["confusion_matrix"]
        report = metrics["classification_report"]
        labels = _labels_from_report(report, matrix)
        derived = _matrix_metrics(matrix, labels)
        _self_check(name, metrics, derived, float(metrics["accuracy"]),
                    float(metrics["macro_f1"]), n_samples)
        models[name] = {
            "accuracy": round(float(metrics["accuracy"]), 6),
            "precision_weighted": round(derived["precision_weighted"], 6),
            "recall_weighted": round(derived["recall_weighted"], 6),
            "f1_weighted": round(float(metrics.get("weighted_f1", derived["f1_weighted"])), 6),
            "f1_macro": round(float(metrics["macro_f1"]), 6),
            "inference_time_ms_per_1000": round(float(metrics["inference_time_per_1000"]), 3),
        }
        best_candidates[name] = float(metrics["macro_f1"])

    best_model = max(best_candidates, key=best_candidates.get)
    if BEST_MODEL_PATH.exists():
        with BEST_MODEL_PATH.open(encoding="utf-8") as f:
            best_info = json.load(f)
        recorded = best_info.get("best_model_name")
        if recorded and recorded != best_model:
            raise ArtifactError(
                f"best_model_info.json says '{recorded}' but recomputing argmax(macro F1) gives "
                f"'{best_model}'."
            )

    best_matrix = metrics_all[best_model]["confusion_matrix"]
    best_labels = _labels_from_report(
        metrics_all[best_model]["classification_report"], best_matrix)
    best_derived = _matrix_metrics(best_matrix, best_labels)

    training_times = _training_times()
    for name in models:
        models[name]["training_time_s"] = training_times.get(name)
        models[name]["n_classes"] = len(best_labels)

    split = summary.get("split_config") or {}
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "dataset": {
            "source": "CIC-IDS2017 (reduced repository copy), held-out test split",
            "n_samples": n_samples,
            "split": {
                "mode": split.get("mode"),
                "ratios": split.get("ratios"),
                "seed": split.get("seed"),
            },
            "note": (
                "Stratified random split of flow records. Metrics describe this held-out "
                "split only: they are not operational-traffic performance and do not "
                "establish real-world generalisation."
            ),
        },
        "labels": best_labels,
        "models": models,
        "best_model": best_model,
        "selection_rule": "highest macro F1 on the held-out test split",
        "confusion_matrix": {
            "model": best_model,
            "rows": "true label",
            "columns": "predicted label",
            "matrix": best_matrix,
            "support": [int(best_derived["per_class"][l]["support"]) for l in best_labels],
            "accuracy": round(best_derived["accuracy"], 8),
            "correct": best_derived["correct"],
            "total": best_derived["total"],
        },
        "per_class": {
            "model": best_model,
            "metrics": best_derived["per_class"],
        },
        "pr_curves": {
            "model": best_model,
            "strategy": "one-vs-rest, sklearn precision_recall_curve",
            "max_points_per_class": MAX_PR_POINTS,
            "curves": _pr_curve_for_model(summary, best_model),
        },
        "zero_day_holdout": summary.get("zero_day_holdout", []),
        "n_holdout_samples": summary.get("n_holdout_samples", 0),
        "zero_day_labels": summary.get("zero_day_labels", []),
        "provenance": {
            "models/metrics.json": str(METRICS_PATH.relative_to(REPO_ROOT)),
            "results/tables/evaluation_summary.json": str(SUMMARY_PATH.relative_to(REPO_ROOT)),
            "pipeline_run.log": (str(TRAIN_LOG_PATH.relative_to(REPO_ROOT))
                                 if TRAIN_LOG_PATH.exists() else "absent"),
        },
        "limitations": [
            "Held-out CIC-IDS2017 split; day-to-day drift means these numbers are not "
            "real-world generalisation.",
            "Severe class imbalance (BENIGN dominates), so accuracy overstates attack "
            "performance; macro F1 and per-class metrics are the load-bearing numbers.",
            "The split was stratified at random per flow rather than by capture day, so "
            "same-day near-duplicate flows can appear in train and test.",
            "Per-sample predicted probabilities and split indices were not persisted; "
            "regenerating them requires re-running preprocessing and evaluation.",
            "Precision-recall curves are for the selected best model only.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUTPUT_PATH), help="output JSON path")
    ap.add_argument("--check-only", action="store_true",
                    help="run the self-checks without writing the file")
    args = ap.parse_args()

    try:
        doc = build()
    except ArtifactError as e:
        print(f"[build_evaluation_json] {e}", file=sys.stderr)
        return 1

    out = Path(args.out)
    if args.check_only:
        print(f"[build_evaluation_json] self-check OK: {len(doc['models'])} models, "
              f"{len(doc['labels'])} classes, {doc['dataset']['n_samples']} test samples, "
              f"best={doc['best_model']}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[build_evaluation_json] wrote {out} "
          f"({out.stat().st_size / 1024:.1f} KiB, best model {doc['best_model']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
