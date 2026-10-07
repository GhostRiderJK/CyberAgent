"""
Tests for preprocessing module.
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


def test_clean_data():
    """Test data cleaning functions."""
    # Create test data with impossible negatives and constant columns
    # Use a feature name that's in the impossible_neg_features list
    data = {
        'Flow Duration': [1.0, 2.0, -1.0, 4.0, 5.0],  # Has negative (impossible)
        'feature2': [0.0, 0.0, 0.0, 0.0, 0.0],        # Constant
        'feature3': [1.0, 1.0, 2.0, 1.0, 1.0],        # Not constant
        'flow_id': [0, 1, 2, 3, 4]  # Note: column name matches metadata
    }
    features_df = pd.DataFrame(data)
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3, 4],  # Note: metadata uses lowercase? Actually from data_loader it's 'flow_id' (no space)
        'other_col': ['a', 'b', 'c', 'd', 'e']
    })

    # Test cleaning
    features_clean, metadata_clean = clean_data(
        features_df, metadata_df,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Check that negative was replaced with NaN
    assert pd.isna(features_clean.loc[2, 'Flow Duration'])
    # Check that constant column was dropped
    assert 'feature2' not in features_clean.columns
    # Check that non-constant columns remain
    assert 'Flow Duration' in features_clean.columns
    assert 'feature3' in features_clean.columns
    # Check that flow_id is preserved (note: column name is 'flow_id' with no space)
    assert 'flow_id' in features_clean.columns
    assert 'flow_id' in metadata_clean.columns  # metadata uses lowercase

    print("clean_data tests passed!")


def test_clean_data_impossible_negatives():
    """Test cleaning of impossible negatives."""
    # Test with a feature that should have negatives removed (Flow Duration)
    data = {
        'Flow Duration': [1.0, 2.0, -1.0, 4.0, 5.0],  # Has negative (impossible)
        'feature2': [0.0, 0.0, 0.0, 0.0, 0.0],        # Constant
        'feature3': [1.0, 1.0, 2.0, 1.0, 1.0],        # Not constant
        'flow_id': [0, 1, 2, 3, 4]
    }
    features_df = pd.DataFrame(data)
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3, 4],
        'other_col': ['a', 'b', 'c', 'd', 'e']
    })

    # Test cleaning
    features_clean, metadata_clean = clean_data(
        features_df, metadata_df,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Check that negative was replaced with NaN
    assert pd.isna(features_clean.loc[2, 'Flow Duration'])
    # Check that constant column was dropped
    assert 'feature2' not in features_clean.columns
    # Check that non-constant columns remain
    assert 'Flow Duration' in features_clean.columns
    assert 'feature3' in features_clean.columns
    # Check that flow_id is preserved
    assert 'flow_id' in features_clean.columns
    assert 'flow_id' in metadata_clean.columns

    print("clean_data impossible negatives test passed!")


def test_clean_data_no_negative_handling():
    """Test cleaning without handling impossible negatives."""
    data = {
        'Flow Duration': [1.0, 2.0, -1.0, 4.0, 5.0],  # Has negative
        'feature2': [0.0, 0.0, 0.0, 0.0, 0.0],        # Constant
        'feature3': [1.0, 1.0, 2.0, 1.0, 1.0],        # Not constant
        'flow_id': [0, 1, 2, 3, 4]
    }
    features_df = pd.DataFrame(data)
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3, 4],
        'other_col': ['a', 'b', 'c', 'd', 'e']
    })

    # Test cleaning WITHOUT handling impossible negatives
    features_clean, metadata_clean = clean_data(
        features_df, metadata_df,
        handle_impossible_negatives=False,  # Don't handle negatives
        drop_constant_columns=True
    )

    # Check that negative was NOT replaced (remains negative)
    assert features_clean.loc[2, 'Flow Duration'] == -1.0
    # Check that constant column was still dropped
    assert 'feature2' not in features_clean.columns
    # Check that flow_id is preserved
    assert 'flow_id' in features_clean.columns
    assert 'flow_id' in metadata_clean.columns

    print("clean_data no negative handling test passed!")


def test_clean_data_duplicate_columns():
    """Test cleaning of duplicate columns."""
    # Test with duplicate column names (similar to debug_dup.py)
    data = {
        'flow_id': [1, 2, 3],  # Note: using lowercase like in actual data
        'Source IP': ['192.168.1.1', '192.168.1.2', '192.168.1.3'],
        'Source Port': [8080, 8081, 8082],
        'Destination IP': ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
        'Destination Port': [80, 443, 80],
        'Protocol': [6, 6, 17],
        'Fwd Header Length': [100, 100, 100],  # First occurrence
        'Fwd Header Length.1': [200, 200, 200],  # Duplicate (should be dropped)
        'Label': ['BENIGN', 'DoS Hulk', 'PortScan']
    }
    features_df = pd.DataFrame(data)
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3],
        'other_col': ['a', 'b', 'c', 'd']
    })

    # Test cleaning - this should drop both columns since they're constant
    features_clean, metadata_clean = clean_data(
        features_df, metadata_df,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Check that BOTH constant columns were dropped (they have nunique=1)
    assert 'Fwd Header Length' not in features_clean.columns
    assert 'Fwd Header Length.1' not in features_clean.columns

    # Check that flow_id is preserved
    assert 'flow_id' in features_clean.columns
    assert 'flow_id' in metadata_clean.columns

    print("clean_data duplicate columns test passed!")


def test_apply_label_grouping_identity():
    """Test label grouping function with empty mapping (identity)."""
    # Create test data with labels - using the same column name format as data_loader
    features_df = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0, 4.0],
        'flow_id': [0, 1, 2, 3]  # This matches what data_loader produces
    })
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3],  # This matches what data_loader produces
        'Label': ['BENIGN', 'DoS Hulk', 'DoS Hulk', 'PortScan']
    })

    # Test identity mapping (empty mapping)
    features_out, metadata_out, mapping = apply_label_grouping(
        features_df, metadata_df, label_mapping_config={}
    )

    # Check that mapping is identity for the labels present
    expected_mapping = {
        'BENIGN': 'BENIGN',
        'DoS Hulk': 'DoS Hulk',
        'PortScan': 'PortScan'
    }
    assert mapping == expected_mapping

    # Check that Label column is in features
    assert 'Label' in features_out.columns
    assert list(features_out['Label']) == ['BENIGN', 'DoS Hulk', 'DoS Hulk', 'PortScan']


def test_apply_label_grouping_webattack():
    """Test label grouping function with Web Attack merging."""
    # Create test data with Web Attack labels (with possible corrupted dash)
    features_df = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        'flow_id': [0, 1, 2, 3, 4, 5]
    })
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3, 4, 5],
        'Label': ['Web Attack \x96 Brute Force', 'Web Attack \x96 XSS', 'Web Attack \x96 Sql Injection', 'BENIGN', 'DoS Hulk', 'PortScan']
    })

    # Test explicit Web Attack mapping
    custom_mapping = {
        'Web Attack - Brute Force': 'Web Attack',
        'Web Attack - XSS': 'Web Attack',
        'Web Attack - Sql Injection': 'Web Attack'
    }
    features_out, metadata_out, mapping = apply_label_grouping(
        features_df, metadata_df, label_mapping_config=custom_mapping
    )

    # The mapping should only include labels present in the data after normalization.
    # Since we pass explicit mapping, we expect it to be returned as-is.
    # However, note that the function first normalizes labels, then applies mapping.
    # The normalization will convert the corrupted dash labels to 'Web Attack - ...'
    # So the keys in the mapping should match the normalized labels.
    # We expect the mapping to be exactly what we passed.
    assert mapping == custom_mapping

    # Check that Label column in features is all 'Web Attack' for the first three, and others unchanged.
    expected_labels = ['Web Attack', 'Web Attack', 'Web Attack', 'BENIGN', 'DoS Hulk', 'PortScan']
    assert list(features_out['Label']) == expected_labels


def test_split_data():
    """Test data splitting function."""
    # Create test data with labels - enough samples per class for stratification
    # We need at least 2 samples per class for the smallest split (test_size=0.25)
    # Let's make 4 samples per class (total 12) so that each split has at least 1 per class.
    features_df = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
        'feature2': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2],
        'flow_id': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        'Label': ['A', 'A', 'A', 'A', 'B', 'B', 'B', 'B', 'C', 'C', 'C', 'C']
    })
    metadata_df = pd.DataFrame({
        'flow_id': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        'other_col': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l']
    })

    # Test stratified split
    (X_train, X_val, X_test,
     y_train, y_val, y_test,
     train_meta, val_meta, test_meta) = split_data(
        features_df, metadata_df,
        split_mode="stratified",
        train_ratio=0.5,
        val_ratio=0.25,
        test_ratio=0.25,
        seed=42
    )

    # Check sizes
    assert len(X_train) == 6  # 50% of 12
    assert len(X_val) == 3    # 25% of 12
    assert len(X_test) == 3   # 25% of 12

    # Check that metadata indices match
    assert len(train_meta) == len(X_train)
    assert len(val_meta) == len(X_val)
    assert len(test_meta) == len(X_test)

    print("split_data tests passed!")


def test_preprocess_train_fit():
    """Test preprocessing fitting function."""
    # Create test training data
    X_train = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0, 4.0, 5.0],
        'feature2': [2.0, 4.0, 6.0, 8.0, 10.0],  # Correlated with feature1
        'feature3': [1.0, 1.0, 1.0, 1.0, 1.0],    # Constant
        'feature4': [0.0, 0.0, 0.0, 0.0, 1.0],    # Near constant
        'flow_id': [0, 1, 2, 3, 4]  # Will be dropped in preprocessing
    })

    # Remove flow_id as it's not a real feature for preprocessing
    X_train = X_train.drop(columns=['flow_id'])

    # Test fitting
    imputer, scaler, feature_mask = preprocess_train_fit(
        X_train,
        correlation_threshold=0.95,
        feature_selection_method="variance",
        top_k_features=2
    )

    # Check that we got the expected objects
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    assert isinstance(imputer, SimpleImputer)
    assert isinstance(scaler, StandardScaler)
    assert isinstance(feature_mask, np.ndarray)

    # Check that constant feature (feature3) was dropped by correlation/variance
    # feature3 is constant, so it should be dropped
    assert not feature_mask[2]  # feature3 should be False in feature mask

    print("preprocess_train_fit tests passed!")


def test_preprocess_transform():
    """Test preprocessing transform function."""
    # Create test data
    X_train = pd.DataFrame({
        'feature1': [1.0, 2.0, 3.0],
        'feature2': [4.0, 5.0, 6.0]
    })

    # Create dummy fitted preprocessors
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    imputer = SimpleImputer(strategy='median')
    scaler = StandardScaler()

    # Fit on dummy data (just to have fitted objects)
    imputer.fit(X_train)
    scaler.fit(imputer.transform(X_train))

    # Create masks (keep all features)
    feature_mask = np.array([True, True])

    # Test transform
    X_transformed = preprocess_transform(X_train, imputer, scaler, feature_mask)

    # Check that we got a DataFrame back
    assert isinstance(X_transformed, pd.DataFrame)
    assert X_transformed.shape == (3, 2)

    print("preprocess_transform tests passed!")


def test_handle_imbalance():
    """Test imbalance handling function."""
    # Create test labels
    y_train = pd.Series(['A', 'A', 'A', 'B', 'B'])  # Imbalanced

    # Test class_weight method
    y_out, info = handle_imbalance(y_train, method="class_weight")

    # Check that labels are unchanged (class weight is used in model)
    assert list(y_out) == ['A', 'A', 'A', 'B', 'B']
    # Check that info contains class weights
    assert 'class_weight' in info
    assert isinstance(info['class_weight'], dict)
    assert len(info['class_weight']) == 2  # Two classes

    print("handle_imbalance tests passed!")


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

    features = base_features.copy()
    features['flow_id'] = range(1000)

    # Merge Label into features for the cleaning function to work properly
    features_with_label = features.merge(metadata[['flow_id', 'Label']], on='flow_id', how='left')

    # Clean data - should drop cross-label rows completely
    features_clean, metadata_clean = clean_data(
        features_with_label, metadata,
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

    # Merge Label into features for the cleaning function to work properly
    features_with_label = features.merge(metadata[['flow_id', 'Label']], on='flow_id', how='left')

    # Store original counts
    original_features_count = len(features)
    original_metadata_count = len(metadata)

    # Clean data - should make NO changes when cross-label >= 0.5%
    features_clean, metadata_clean = clean_data(
        features_with_label, metadata,
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
    test_clean_data()
    test_clean_data_impossible_negatives()
    test_clean_data_no_negative_handling()
    test_clean_data_duplicate_columns()
    test_apply_label_grouping_identity()
    test_apply_label_grouping_webattack()
    test_split_data()
    test_preprocess_train_fit()
    test_preprocess_transform()
    test_handle_imbalance()
    test_clean_data_cross_label_under_threshold()
    test_clean_data_cross_label_over_threshold()
    test_clean_data_end_to_end_fit_transform()
    print("All preprocessing tests passed!")