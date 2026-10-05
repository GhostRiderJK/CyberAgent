"""
Tests for dataset reduction functionality.
"""
import sys
import os
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.reduce_dataset import reduce_dataset, save_reduced_dataset, load_and_reduce_data
from src.cyberagent.data_loader import generate_synthetic_data
from src.cyberagent.config import config

def test_reduce_dataset():
    """Test dataset reduction function."""
    # Generate synthetic data with known class distribution
    features_df, metadata_df = generate_synthetic_data(n_samples=1000, random_state=42)

    # Add Label column to features_df for testing (as would happen after merge)
    features_df['Label'] = metadata_df['Label'].values

    # Setup logger
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    logger.info(f"Original dataset shape: {features_df.shape}")
    logger.info(f"Original label distribution:\n{features_df['Label'].value_counts()}")

    # Apply reduction with small caps for testing
    reduced_features_df, reduced_metadata_df = reduce_dataset(
        features_df, metadata_df,
        benign_cap=100,  # Keep max 100 BENIGN
        attack_cap=50,   # Keep max 50 per attack class
        seed=42
    )

    # Check that we have the expected columns
    assert 'Label' in reduced_features_df.columns
    assert 'flow_id' in reduced_features_df.columns
    assert 'flow_id' in reduced_metadata_df.columns

    # Check shapes
    assert len(reduced_features_df) == len(reduced_metadata_df)
    assert len(reduced_features_df) <= 1000  # Should be reduced

    # Check that BENIGN is capped at 100
    benign_count = (reduced_features_df['Label'] == 'BENIGN').sum()
    assert benign_count <= 100

    # Check that each attack class is capped at 50
    attack_labels = reduced_features_df[reduced_features_df['Label'] != 'BENIGN']['Label'].unique()
    for label in attack_labels:
        count = (reduced_features_df['Label'] == label).sum()
        assert count <= 50, f"Label {label} has {count} samples, exceeding cap of 50"

    # Check that flow_id is sequential and matches
    assert list(reduced_features_df['flow_id']) == list(range(len(reduced_features_df)))
    assert list(reduced_metadata_df['flow_id']) == list(range(len(reduced_metadata_df)))

    print("reduce_dataset tests passed!")

def test_save_reduced_dataset():
    """Test saving reduced dataset."""
    # Generate and reduce data
    features_df, metadata_df = generate_synthetic_data(n_samples=100, random_state=42)
    features_df['Label'] = metadata_df['Label'].values

    reduced_features_df, reduced_metadata_df = reduce_dataset(
        features_df, metadata_df,
        benign_cap=50,
        attack_cap=25,
        seed=42
    )

    # Test saving
    with tempfile.TemporaryDirectory() as temp_dir:
        features_path = Path(temp_dir) / "test_features.parquet"
        metadata_path = Path(temp_dir) / "test_metadata.parquet"

        save_reduced_dataset(
            reduced_features_df, reduced_metadata_df,
            features_path=str(features_path),
            metadata_path=str(metadata_path)
        )

        # Check that files exist
        assert features_path.exists()
        assert metadata_path.exists()

        # Check that we can load them back
        loaded_features = pd.read_parquet(features_path)
        loaded_metadata = pd.read_parquet(metadata_path)

        assert len(loaded_features) == len(reduced_features_df)
        assert len(loaded_metadata) == len(reduced_metadata_df)

        # Check that key columns are preserved
        assert 'Label' in loaded_features.columns
        assert 'flow_id' in loaded_features.columns
        assert 'flow_id' in loaded_metadata.columns

    print("save_reduced_dataset tests passed!")

def test_load_and_reduce_data():
    """Test the convenience function."""
    # Test with synthetic data
    reduced_features_df, reduced_metadata_df = load_and_reduce_data(
        synthetic=True,
        benign_cap=50,
        attack_cap=25,
        seed=42
    )

    # Check basic properties
    assert len(reduced_features_df) == len(reduced_metadata_df)
    assert 'Label' in reduced_features_df.columns
    assert 'flow_id' in reduced_features_df.columns

    # Check that reduction worked
    benign_count = (reduced_features_df['Label'] == 'BENIGN').sum()
    assert benign_count <= 50

    print("load_and_reduce_data tests passed!")

if __name__ == "__main__":
    test_reduce_dataset()
    test_save_reduced_dataset()
    test_load_and_reduce_data()
    print("All reduction tests passed!")