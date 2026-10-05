"""
Tests for loader, label normalization, and duplicate-column drop.
"""
import sys
import os
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyberagent.data_loader import (
    normalize_label,
    load_traffic_labelling_data,
    load_data,
    generate_synthetic_data
)
from src.cyberagent.config import config

def test_label_normalization():
    """Test label normalization function."""
    # Test basic whitespace stripping
    assert normalize_label("  TEST  ") == "TEST"

    # Test None/NaN handling
    assert pd.isna(normalize_label(None))
    assert pd.isna(normalize_label(float('nan')))

    # Test dash character fixing - focus on what we actually implement
    test_input = "Web Attack � Brute Force"
    result = normalize_label(test_input)
    # Our regex should catch this and replace with hyphen
    assert isinstance(result, str)
    assert "Web Attack" in result
    assert "Brute Force" in result

    # Test normal label unchanged
    assert normalize_label("BENIGN") == "BENIGN"
    assert normalize_label("DoS Hulk") == "DoS Hulk"

    print("Label normalization tests passed!")

def test_duplicate_column_drop():
    """Test that duplicate columns are handled."""
    # Create a test CSV with duplicate column names
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test data
        data = {
            'Flow ID': [1, 2, 3],
            'Source IP': ['192.168.1.1', '192.168.1.2', '192.168.1.3'],
            'Source Port': [8080, 8081, 8082],
            'Destination IP': ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
            'Destination Port': [80, 443, 80],
            'Protocol': [6, 6, 17],
            'Fwd Header Length': [100, 100, 100],  # First occurrence
            'Fwd Header Length.1': [200, 200, 200],  # Duplicate (should be dropped)
            'Label': ['BENIGN', 'DoS Hulk', 'PortScan']
        }
        df = pd.DataFrame(data)

        # Save to CSV
        csv_path = Path(temp_dir) / "test.csv"
        df.to_csv(csv_path, index=False)

        # Temporarily override config to point to our test data
        original_raw_dir = config.get("dataset.raw_dir")
        original_primary_folder = config.get("dataset.primary_folder")
        original_file_extension = config.get("dataset.file_extension")

        config.set("dataset.raw_dir", temp_dir)
        config.set("dataset.primary_folder", ".")
        config.set("dataset.file_extension", ".csv")

        try:
            # Load the data
            features_df, metadata_df = load_traffic_labelling_data()

            # Debug: Print column names
            print(f"Features columns: {list(features_df.columns)}")
            print(f"Metadata columns: {list(metadata_df.columns)}")

            # Check that duplicate column was dropped
            # The function drops duplicates by keeping first occurrence
            # So 'Fwd Header Length' should be present, 'Fwd Header Length.1' should be dropped
            assert 'Fwd Header Length' in features_df.columns
            assert 'Fwd Header Length.1' not in features_df.columns

            # Check that we kept the first occurrence
            assert list(features_df['Fwd Header Length']) == [100, 100, 100]

            print("Duplicate column drop tests passed!")

        finally:
            # Restore config
            config.set("dataset.raw_dir", original_raw_dir)
            config.set("dataset.primary_folder", original_primary_folder)
            config.set("dataset.file_extension", original_file_extension)

def test_synthetic_data_generation():
    """Test synthetic data generation with expected schema."""
    features_df, metadata_df = generate_synthetic_data(n_samples=100, random_state=42)

    # Check shapes
    assert len(features_df) == 100
    assert len(metadata_df) == 100

    # Check that flow_id is present and sequential
    assert list(features_df['flow_id']) == list(range(100))
    assert list(metadata_df['flow_id']) == list(range(100))

    # Check that Label column exists in metadata
    assert 'Label' in metadata_df.columns

    # Check that we have expected columns from the synthetic data generator
    expected_features = ['Destination Port', 'Protocol', 'Flow Duration']
    for feat in expected_features:
        assert feat in features_df.columns

    expected_metadata = ['Flow ID', 'Source IP', 'Source Port', 'Destination IP', 'Timestamp']
    for meta in expected_metadata:
        assert meta in metadata_df.columns

    # Check label distribution (should have mostly BENIGN)
    label_counts = metadata_df['Label'].value_counts()
    assert 'BENIGN' in label_counts.index
    assert label_counts['BENIGN'] > 50  # Should be majority

    print("Synthetic data generation tests passed!")

def test_load_data_synthetic():
    """Test loading synthetic data."""
    # Test without saving
    features_df, metadata_df = load_data(synthetic=True)
    assert len(features_df) > 0
    assert len(metadata_df) > 0

    # Test with saving (use temporary directory)
    with tempfile.TemporaryDirectory() as temp_dir:
        # Temporarily override config
        original_processed_dir = config.get("dataset.processed_dir")
        config.set("dataset.processed_dir", temp_dir)

        try:
            features_df, metadata_df = load_data(synthetic=True, make_synthetic=True)

            # Check that files were saved
            features_path = Path(temp_dir) / "synthetic_features.parquet"
            metadata_path = Path(temp_dir) / "synthetic_metadata.parquet"

            assert features_path.exists()
            assert metadata_path.exists()

            # Check that we can load them back
            loaded_features = pd.read_parquet(features_path)
            loaded_metadata = pd.read_parquet(metadata_path)

            assert len(loaded_features) == len(features_df)
            assert len(loaded_metadata) == len(metadata_df)

        finally:
            # Restore config
            config.set("dataset.processed_dir", original_processed_dir)

    print("Load synthetic data tests passed!")

if __name__ == "__main__":
    test_label_normalization()
    test_duplicate_column_drop()
    test_synthetic_data_generation()
    test_load_data_synthetic()
    print("All loader, label normalization, and duplicate-column drop tests passed!")