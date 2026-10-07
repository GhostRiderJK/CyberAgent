"""
Test for determinism in data splitting.
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyberagent.preprocess import (
    load_reduced_data,
    apply_label_grouping,
    clean_data,
    split_data
)
from src.cyberagent.config import config


def test_split_determinism():
    """Test that splitting with the same seed produces identical results."""
    # Load data
    features_df, metadata_df = load_reduced_data()

    # Apply label grouping and cleaning (same as in example pipeline)
    features_with_label, metadata_with_label, _ = apply_label_grouping(
        features_df, metadata_df
    )

    features_clean, metadata_clean = clean_data(
        features_with_label, metadata_with_label,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Split data twice with the same seed
    split1 = split_data(
        features_clean, metadata_clean,
        split_mode="stratified",
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        seed=42
    )

    split2 = split_data(
        features_clean, metadata_clean,
        split_mode="stratified",
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        seed=42
    )

    # Unpack splits
    (X_train1, X_val1, X_test1,
     y_train1, y_val1, y_test1,
     train_meta1, val_meta1, test_meta1) = split1

    (X_train2, X_val2, X_test2,
     y_train2, y_val2, y_test2,
     train_meta2, val_meta2, test_meta2) = split2

    # Assert that flow_id sets are identical for each split
    assert set(X_train1.index) == set(X_train2.index), "Train flow_id sets differ"
    assert set(X_val1.index) == set(X_val2.index), "Validation flow_id sets differ"
    assert set(X_test1.index) == set(X_test2.index), "Test flow_id sets differ"

    # Also assert that the actual data is identical
    pd.testing.assert_frame_equal(X_train1.sort_index(), X_train2.sort_index())
    pd.testing.assert_frame_equal(X_val1.sort_index(), X_val2.sort_index())
    pd.testing.assert_frame_equal(X_test1.sort_index(), X_test2.sort_index())

    pd.testing.assert_series_equal(y_train1.sort_index(), y_train2.sort_index())
    pd.testing.assert_series_equal(y_val1.sort_index(), y_val2.sort_index())
    pd.testing.assert_series_equal(y_test1.sort_index(), y_test2.sort_index())

    print("split determinism test passed!")


if __name__ == "__main__":
    test_split_determinism()
    print("All determinism tests passed!")