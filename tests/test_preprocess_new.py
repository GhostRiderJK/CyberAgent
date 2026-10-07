"""
Tests for preprocessing module - new tests for cross-label duplicate handling.
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyberagent.preprocess import (
    load_reduced_data,
    clean_data,
    apply_label_grouping,
    split_data,
    preprocess_train_fit,
    preprocess_transform,
    handle_imbalance
)
from src.cyberagent.data_loader import generate_synthetic_data
from src.cyberagent.config import config


def test_clean_data_cross_label_under_threshold():
    """Test duplicate handling when cross-label rows are under 0.5% threshold."""
    # Create test data with mostly same-label duplicates and a few cross-label duplicates
    # Total rows: 1000
    # Same-label duplicates: 996 rows in 498 groups (2 rows each)
    # Cross-label duplicates: 4 rows in 2 groups (2 rows each) = 0.4% of total
    # Expected: Cross-label rows dropped completely, same-label groups kept 1 row each

    import numpy as np

    # Create base features that will produce duplicates
    # 500 groups, each with 2 identical rows
    base_features_list = []
    for i in range(500):
        base_features_list.append({'feat1': float(i*10), 'feat2': 0.0})  # First in group
        base_features_list.append({'feat1': float(i*10), 'feat2': 0.0})  # Second in group
    base_features = pd.DataFrame(base_features_list)

    # Create metadata with labels
    # Groups 0-497: same-label duplicates (all BENIGN)
    # Group 498: cross-label (BENIGN/DoS Hulk)
    # Group 499: cross-label (PortScan/DoS Hulk)
    labels = []
    # Same-label groups: 498 groups × 2 rows each = 996 rows of BENIGN
    labels.extend(['BENIGN'] * 996)
    # Cross-label group 1: BENIGN, DoS Hulk
    labels.extend(['BENIGN', 'DoS Hulk'])
    # Cross-label group 2: PortScan, DoS Hulk
    labels.extend(['PortScan', 'DoS Hulk'])

    metadata = pd.DataFrame({
        'flow_id': range(1000),
        'Label': labels
    })

    # Note: We do NOT merge Label into features here; let clean_data do it
    features = base_features.copy()
    features['flow_id'] = range(1000)

    # Clean data - should drop cross-label rows completely
    features_clean, metadata_clean = clean_data(
        features, metadata,
        handle_impossible_negatives=False,  # Keep it simple
        drop_constant_columns=False
    )

    # Check results:
    # Original: 1000 rows
    # Same-label groups: 498 groups → keep 1 row each = 498 rows
    # Cross-label groups: 2 groups → drop ALL rows = 0 rows kept
    # Expected total: 498 rows kept

    assert len(features_clean) == 498
    assert len(metadata_clean) == 498

    # Verify no cross-label contamination remains (all remaining labels should be BENIGN)
    labels_clean = set(metadata_clean['Label'].unique())
    expected_labels = {'BENIGN'}
    assert labels_clean == expected_labels

    print("cross-label under threshold test passed!")


def test_clean_data_cross_label_over_threshold():
    """Test duplicate handling when cross-label rows are over 0.5% threshold."""
    # Create test data with significant cross-label duplicates
    # Total rows: 100
    # Same-label duplicates: 10 rows in 5 groups (2 rows each)
    # Cross-label duplicates: 90 rows in 45 groups (2 rows each) = 90% of total
    # Expected: No changes made (keep existing behavior - drop duplicates keeping first)

    import numpy as np

    # Create features for 50 groups total (5 same-label + 45 cross-label)
    base_features_list = []
    labels_list = []
    flow_id = 0

    # Same-label groups: 5 groups, 2 rows each, same label
    for i in range(5):
        base_features_list.append({'feat1': float(i*10), 'feat2': 0.0})
        base_features_list.append({'feat1': float(i*10), 'feat2': 0.0})
        labels_list.extend(['BENIGN', 'BENIGN'])
        flow_id += 2

    # Cross-label groups: 45 groups, 2 rows each, different labels
    for i in range(45):
        base_features_list.append({'feat1': float(100 + i*10), 'feat2': 1.0})
        base_features_list.append({'feat1': float(100 + i*10), 'feat2': 1.0})
        labels_list.extend(['BENIGN', 'DoS Hulk'])
        flow_id += 2

    features = pd.DataFrame(base_features_list)
    features['flow_id'] = range(len(features))

    metadata = pd.DataFrame({
        'flow_id': range(len(features)),
        'Label': labels_list
    })

    # Note: We do NOT merge Label into features here; let clean_data do it
    # Store original counts
    original_features_count = len(features)
    original_metadata_count = len(metadata)

    # Clean data - should make NO changes when cross-label >= 0.5%
    features_clean, metadata_clean = clean_data(
        features, metadata,
        handle_impossible_negatives=False,
        drop_constant_columns=False
    )

    # Should keep all original rows (no changes made)
    assert len(features_clean) == original_features_count
    assert len(metadata_clean) == original_metadata_count

    print("cross-label over threshold test passed!")


def test_clean_data_end_to_end_fit_transform():
    """Test end-to-end fit then transform workflow."""
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    # Create test data
    X_train = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0, 4.0, 5.0],
        'feature2': [2.0, 4.0, 6.0, 8.0, 10.0],  # Correlated with feature1
        'feature3': [1.0, 1.0, 1.0, 1.0, 1.0],    # Constant
        'feature4': [0.0, 0.0, 0.0, 0.0, 1.0],    # Near constant
    })

    # Test fitting
    imputer, scaler, feature_mask = preprocess_train_fit(
        X_train,
        correlation_threshold=0.95,
        feature_selection_method="variance",
        top_k_features=2
    )

    # Test transforming training data
    X_train_transformed = preprocess_transform(X_train, imputer, scaler, feature_mask)
    assert isinstance(X_train_transformed, pd.DataFrame)

    # Test transforming new data
    X_new = pd.DataFrame({
        'feature1': [1.5, 2.5],
        'feature2': [3.0, 5.0],
        'feature3': [1.0, 1.0],
        'feature4': [0.0, 1.0]
    })
    X_new_transformed = preprocess_transform(X_new, imputer, scaler, feature_mask)
    assert isinstance(X_new_transformed, pd.DataFrame)
    assert X_new_transformed.shape[1] == X_train_transformed.shape[1]  # Same number of features

    print("end-to-end fit-transform test passed!")


if __name__ == "__main__":
    test_clean_data_cross_label_under_threshold()
    test_clean_data_cross_label_over_threshold()
    test_clean_data_end_to_end_fit_transform()
    print("All new preprocessing tests passed!")