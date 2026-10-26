#!/usr/bin/env python
"""
Run the preprocessing pipeline and persist its artifacts.

Produces:
  data/processed/holdout_zero_day.parquet + meta
  data/processed/preprocess_artifacts.joblib  (imputer, scaler, feature_mask, feature_names)
  results/tables/selected_features.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib

from cyberagent.config import config
from cyberagent.logging_setup import logger
from cyberagent.preprocess import example_preprocessing_pipeline


def main():
    logger.info("Running preprocessing pipeline...")
    data = example_preprocessing_pipeline(save_outputs=True)

    # The imputer/scaler were fitted on the FULL pre-selection feature frame;
    # data["X_train"] is already post-selection. feature_names_in_ preserves the
    # original names the estimator was fitted with.
    full_names = list(data["imputer"].feature_names_in_)

    artifacts = {
        "imputer": data.get("imputer"),
        "scaler": data.get("scaler"),
        "feature_mask": data.get("feature_mask"),
        "feature_names": full_names,                       # full pre-selection column set
        "selected_feature_names": list(data["X_test"].columns),  # final model columns, in order
    }
    out = Path(config.get("dataset.processed_dir")) / "preprocess_artifacts.joblib"
    joblib.dump(artifacts, out)
    logger.info(f"Saved preprocessing artifacts to {out}")

    logger.info(
        f"Preprocessing complete. Train: {data['X_train'].shape}, "
        f"Val: {data['X_val'].shape}, Test: {data['X_test'].shape}, "
        f"classes: {sorted(data['y_train'].unique())}"
    )


if __name__ == "__main__":
    main()
