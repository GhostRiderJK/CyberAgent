#!/usr/bin/env python
"""
Full evaluation runner for CyberAgent.

For every trained model in models/ this computes, on the held-out test split:
  - accuracy, macro/weighted F1, macro precision/recall
  - per-class precision/recall/F1/support (classification report)
  - confusion matrix figure
and, using the saved zero-day holdout (Heartbleed / Infiltration, never seen
during training), an unseen-class generalisation report per model.

Outputs:
  results/tables/model_comparison.csv|md
  results/tables/per_class_metrics_<model>.csv
  results/tables/zero_day_holdout_results.csv|md
  results/tables/evaluation_summary.json
  results/figures/confusion_matrix_<model>.png
  results/figures/zero_day_holdout_f1.png
"""
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")

from cyberagent.config import config
from cyberagent.logging_setup import logger
from cyberagent.preprocess import example_preprocessing_pipeline
from cyberagent.evaluate import (
    evaluate_model,
    calculate_metrics,
    compare_models,
    plot_confusion_matrix,
    save_evaluation_results,
)

MODELS_DIR = Path("models")
TABLES_DIR = Path("results/tables")
FIGURES_DIR = Path("results/figures")


def to_native(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_native(v) for v in obj]
    return obj


def model_feature_frame(X: pd.DataFrame, model, expected_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """Align evaluation columns to the order the model was fitted on.

    LightGBM/XGBoost mangle spaces to underscores in feature_names_in_, so we
    rely on the deterministic pipeline column order (expected_cols) instead.
    """
    cols = expected_cols if expected_cols else list(X.columns)
    missing = [c for c in cols if c not in X.columns]
    if missing:
        raise ValueError(f"Model expects features absent from evaluation data: {missing[:5]}")
    return X[cols]


def predict_labels(model, X: pd.DataFrame) -> np.ndarray:
    """Predict with label decoding (LGBM/XGB store an internal LabelEncoder)."""
    pred = model.predict(X)
    le = getattr(model, "label_encoder_", None)
    return le.inverse_transform(pred) if le is not None else pred


def transform_holdout(holdout: pd.DataFrame, artifacts: dict) -> pd.DataFrame:
    """Apply the saved imputer/scaler/feature-mask to the holdout feature frame."""
    feature_names = artifacts["feature_names"]
    X = holdout.drop(columns=[c for c in ("flow_id", "Label") if c in holdout.columns])
    X = X.replace([np.inf, -np.inf], np.nan)
    X = pd.DataFrame(
        artifacts["scaler"].transform(artifacts["imputer"].transform(X)),
        columns=X.columns, index=X.index,
    )
    return X[feature_names]


def per_class_table(report: dict, model_name: str) -> pd.DataFrame:
    rows = []
    for label, m in report.items():
        if label in ("accuracy", "macro avg", "weighted avg"):
            if isinstance(m, dict) and "f1-score" in m:
                rows.append({"model": model_name, "class": label,
                             "precision": m.get("precision", ""),
                             "recall": m.get("recall", ""),
                             "f1": m.get("f1-score", ""),
                             "support": m.get("support", "")})
            continue
        rows.append({"model": model_name, "class": label,
                     "precision": m.get("precision", ""),
                     "recall": m.get("recall", ""),
                     "f1": m.get("f1-score", ""),
                     "support": m.get("support", "")})
    return pd.DataFrame(rows)


def main():
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=== CyberAgent: evaluate ===")

    data = example_preprocessing_pipeline(save_outputs=False)
    X_test, y_test = data["X_test"], data["y_test"]

    artifacts_path = Path(config.get("dataset.processed_dir")) / "preprocess_artifacts.joblib"
    holdout_features_path = Path(config.get("dataset.processed_dir")) / "holdout_zero_day.parquet"
    holdout_available = artifacts_path.exists() and holdout_features_path.exists()
    selected_cols = None
    if artifacts_path.exists():
        artifacts = joblib.load(artifacts_path)
        selected_cols = artifacts.get("selected_feature_names")
    if holdout_available:
        holdout = pd.read_parquet(holdout_features_path)
        X_holdout_raw = transform_holdout(holdout, artifacts)
        y_holdout = holdout["Label"].reset_index(drop=True)
        logger.info(f"Zero-day holdout: {X_holdout_raw.shape[0]} rows, labels: {sorted(y_holdout.unique())}")
    else:
        logger.warning("Holdout artifacts missing; run `make preprocess` first. Skipping zero-day evaluation.")

    model_files = sorted(MODELS_DIR.glob("*.joblib"))
    model_files = [m for m in model_files
                   if m.stem in (config.get("training.models") or [])
                   and "isolation_forest" not in m.stem]
    if not model_files:
        raise SystemExit("No trained models found in models/. Run `make train` first.")

    test_results, holdout_rows, per_class_rows = {}, [], []

    for mf in model_files:
        name = mf.stem
        logger.info(f"--- Evaluating {name} ---")
        model = joblib.load(mf)
        X = model_feature_frame(X_test, model, selected_cols)

        metrics = evaluate_model(model, X, y_test, name)
        test_results[name] = metrics

        # Per-class metrics table
        pc = per_class_table(metrics["classification_report"], name)
        per_class_rows.append(pc)
        pc.to_csv(TABLES_DIR / f"per_class_metrics_{name}.csv", index=False)

        # Confusion matrix figure
        cm = np.array(metrics["confusion_matrix"])
        class_names = sorted(set(y_test.unique()))
        fig = plot_confusion_matrix(
            cm, class_names,
            title=f"Confusion matrix - {name} (test set)",
            figsize=(max(8, len(class_names) * 1.1), 7),
            save_path=str(FIGURES_DIR / f"confusion_matrix_{name}.png"),
        )
        import matplotlib.pyplot as plt
        plt.close(fig)

        # Zero-day holdout evaluation
        if holdout_available:
            try:
                Xh = model_feature_frame(X_holdout_raw.reset_index(drop=True), model, selected_cols)
                yh_pred = predict_labels(model, Xh)
                hm = calculate_metrics(y_holdout.values, yh_pred)
                holdout_rows.append({
                    "model": name,
                    "accuracy": hm["accuracy"],
                    "macro_f1": hm["macro_f1"],
                    "per_class_f1": {k: v.get("f1-score") for k, v in hm["classification_report"].items()
                                     if isinstance(v, dict) and "f1-score" in v},
                })
                per_class_rows.append(per_class_table(hm["classification_report"], f"{name} (zero-day)"))
                logger.info(f"{name} zero-day holdout macro F1: {hm['macro_f1']:.4f}")
            except Exception as e:
                logger.error(f"Zero-day evaluation failed for {name}: {e}")

    # Model comparison (test set)
    comparison_df = compare_models(test_results)
    comparison_df.to_csv(TABLES_DIR / "model_comparison.csv", index=False)
    with open(TABLES_DIR / "model_comparison.md", "w", encoding="utf-8") as f:
        f.write(comparison_df.to_markdown(index=False))

    all_per_class = pd.concat(per_class_rows, ignore_index=True)
    all_per_class.to_csv(TABLES_DIR / "per_class_metrics_all.csv", index=False)

    # Zero-day tables + figure
    if holdout_rows:
        hz_df = pd.DataFrame([{k: v for k, v in r.items() if k != "per_class_f1"} for r in holdout_rows])
        hz_df.to_csv(TABLES_DIR / "zero_day_holdout_results.csv", index=False)
        with open(TABLES_DIR / "zero_day_holdout_results.md", "w", encoding="utf-8") as f:
            f.write(hz_df.to_markdown(index=False))

        fig, ax = plt.subplots(figsize=(8, 5))
        # Flatten per-class F1 for the attack classes present in holdout
        holdout_classes = sorted(set().union(*[set(r["per_class_f1"]) for r in holdout_rows]))
        width = 0.8 / max(1, len(holdout_classes))
        for ci, cls in enumerate(holdout_classes):
            vals = [r["per_class_f1"].get(cls, 0.0) for r in holdout_rows]
            ax.bar(np.arange(len(holdout_rows)) + ci * width, vals, width, label=cls)
        ax.set_xticks(np.arange(len(holdout_rows)) + width * (len(holdout_classes) - 1) / 2)
        ax.set_xticklabels([r["model"] for r in holdout_rows])
        ax.set_ylabel("F1 (unseen attack classes)")
        ax.set_title("Zero-day holdout performance")
        ax.legend()
        fig.savefig(FIGURES_DIR / "zero_day_holdout_f1.png", bbox_inches="tight", dpi=300)
        plt.close(fig)

    summary = {
        "test_set": test_results,
        "zero_day_holdout": holdout_rows,
        "n_test_samples": int(len(X_test)),
        "n_holdout_samples": int(len(y_holdout)) if holdout_available else 0,
        "split_config": {
            "mode": config.get("split.mode"),
            "ratios": [config.get("split.train_ratio"), config.get("split.val_ratio"), config.get("split.test_ratio")],
            "seed": config.get("split.seed"),
        },
        "zero_day_labels": config.get("preprocessing.zero_day_holdout_labels", []),
    }
    with open(TABLES_DIR / "evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(to_native(summary), f, indent=2)

    best = comparison_df.loc[comparison_df["Macro F1"].idxmax()]
    logger.info("EVALUATION COMPLETE")
    logger.info(f"Best model on test set: {best['Model']} (macro F1 {best['Macro F1']:.4f})")
    logger.info(f"Tables -> {TABLES_DIR}, figures -> {FIGURES_DIR}")


if __name__ == "__main__":
    main()
