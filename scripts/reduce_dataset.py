"""
Dataset reduction script for CyberAgent.
Reduces dataset size while preserving rare attack classes.
"""
import sys
import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from typing import Tuple
import yaml
from src.cyberagent.config import config
from src.cyberagent.logging_setup import logger
from src.cyberagent.data_loader import load_data


def normalize_label(label):
    """Normalize label by stripping control characters and handling Web Attack variants."""
    if pd.isna(label):
        return label
    # Strip control characters and normalize whitespace
    label_str = str(label)
    # Remove control characters (including \x96 which appears as \xc2\x96 in UTF-8 bytes)
    label_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', label_str)
    # Collapse multiple whitespace to single space
    label_str = re.sub(r'\s+', ' ', label_str).strip()
    # Handle Web Attack variants - ensure proper dash after "Web Attack"
    # Only add dash if not already present
    if not label_str.startswith('Web Attack - '):
        label_str = re.sub(r'^Web Attack\s*', 'Web Attack - ', label_str)
    return label_str

def reduce_dataset(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    benign_cap: int = None,
    attack_cap: int = None,
    seed: int = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reduce dataset size while preserving rare attack classes.

    Args:
        features_df: DataFrame with features and Label column
        metadata_df: DataFrame with metadata
        benign_cap: Maximum number of BENIGN samples to keep
        attack_cap: Maximum number of samples per attack class to keep
        seed: Random seed for reproducibility

    Returns:
        Tuple of (reduced_features_df, reduced_metadata_df)
    """
    if benign_cap is None:
        benign_cap = config.get("reduction.benign_cap", 300000)
    if attack_cap is None:
        attack_cap = config.get("reduction.attack_cap", 50000)
    if seed is None:
        seed = config.get("reduction.seed", config.get("seed", 42))

    logger.info(f"Starting dataset reduction with benign_cap={benign_cap}, attack_cap={attack_cap}, seed={seed}")
    logger.info(f"Original dataset shape: {features_df.shape}")

    # Ensure Label column exists in features_df (it should be there from data_loader)
    if 'Label' not in features_df.columns:
        # If Label is only in metadata_df, we need to merge
        if 'Label' in metadata_df.columns:
            # Merge Label from metadata_df into features_df using flow_id
            features_df = features_df.merge(
                metadata_df[['flow_id', 'Label']],
                on='flow_id',
                how='left'
            )
        else:
            raise ValueError("Label column not found in either features_df or metadata_df")

    # Get class distribution before reduction
    label_counts = features_df['Label'].value_counts()
    logger.info(f"Class distribution before reduction:\n{label_counts}")

    # Normalize labels to handle control characters and Web Attack variants
    def normalize_label(label):
        if pd.isna(label):
            return label
        import re
        # Strip control characters and normalize whitespace
        label_str = str(label)
        # Remove control characters (including \x96 which appears as \xc2\x96 in UTF-8 bytes)
        label_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', label_str)
        # Collapse multiple whitespace to single space
        label_str = re.sub(r'\s+', ' ', label_str).strip()
        # Handle Web Attack variants - ensure proper dash after "Web Attack"
        # Only add dash if not already present
        if not label_str.startswith('Web Attack - '):
            label_str = re.sub(r'^Web Attack\s*', 'Web Attack - ', label_str)
        return label_str

    # Apply normalization to labels
    features_df['Label'] = features_df['Label'].apply(normalize_label)

    # Get updated label counts after normalization
    label_counts = features_df['Label'].value_counts()
    logger.info(f"Class distribution after label normalization:\n{label_counts}")

    # List to hold reduced dataframes
    reduced_dfs = []
    reduced_metadata_dfs = []

    # Process each class
    for label, count in label_counts.items():
        logger.info(f"Processing class '{label}' with {count} samples")

        # Get indices for this class
        class_indices = features_df[features_df['Label'] == label].index

        if label == 'BENIGN':
            # Apply benign cap
            if len(class_indices) > benign_cap:
                logger.info(f"Downsampling BENIGN from {len(class_indices)} to {benign_cap}")
                # Randomly sample benign_cap indices
                np.random.seed(seed)
                selected_indices = np.random.choice(class_indices, size=benign_cap, replace=False)
            else:
                logger.info(f"Keeping all BENIGN samples ({len(class_indices)}) as it's under cap")
                selected_indices = class_indices
        else:
            # Apply attack cap
            if len(class_indices) > attack_cap:
                logger.info(f"Downsampling {label} from {len(class_indices)} to {attack_cap}")
                # Randomly sample attack_cap indices
                np.random.seed(seed + hash(label) % 1000)  # Different seed for each class
                selected_indices = np.random.choice(class_indices, size=attack_cap, replace=False)
            else:
                logger.info(f"Keeping all {label} samples ({len(class_indices)}) as it's under cap")
                selected_indices = class_indices

        # Select the data for this class
        reduced_features_df = features_df.loc[selected_indices].copy()
        reduced_metadata_df = metadata_df.loc[selected_indices].copy()

        reduced_dfs.append(reduced_features_df)
        reduced_metadata_dfs.append(reduced_metadata_df)

    # Concatenate all reduced data
    if reduced_dfs:
        final_features_df = pd.concat(reduced_dfs, ignore_index=True)
        final_metadata_df = pd.concat(reduced_metadata_dfs, ignore_index=True)
    else:
        final_features_df = pd.DataFrame()
        final_metadata_df = pd.DataFrame()

    # Shuffle the final dataset
    logger.info("Shuffling reduced dataset...")
    np.random.seed(seed)
    shuffle_indices = np.random.permutation(len(final_features_df))
    final_features_df = final_features_df.iloc[shuffle_indices].reset_index(drop=True)
    final_metadata_df = final_metadata_df.iloc[shuffle_indices].reset_index(drop=True)

    # Update flow_id to be sequential in the reduced dataset
    final_features_df['flow_id'] = range(len(final_features_df))
    final_metadata_df['flow_id'] = range(len(final_metadata_df))

    # Get class distribution after reduction
    final_label_counts = final_features_df['Label'].value_counts()
    logger.info(f"Class distribution after reduction:\n{final_label_counts}")
    logger.info(f"Reduced dataset shape: {final_features_df.shape}")

    return final_features_df, final_metadata_df

def save_reduced_dataset(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    features_path: str = None,
    metadata_path: str = None
) -> None:
    """
    Save reduced dataset to Parquet files.

    Args:
        features_df: DataFrame with features
        metadata_df: DataFrame with metadata
        features_path: Path to save features Parquet file
        metadata_path: Path to save metadata Parquet file
    """
    if features_path is None:
        features_path = config.get("dataset.processed_dir") + "/flows_features.parquet"
    if metadata_path is None:
        metadata_path = config.get("dataset.processed_dir") + "/flows_meta.parquet"

    # Ensure directory exists
    Path(features_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Saving features to {features_path}")
    features_df.to_parquet(features_path, compression='zstd')

    logger.info(f"Saving metadata to {metadata_path}")
    metadata_df.to_parquet(metadata_path, compression='zstd')

    # Log file sizes
    features_size = os.path.getsize(features_path) / (1024 * 1024)  # MB
    metadata_size = os.path.getsize(metadata_path) / (1024 * 1024)  # MB
    logger.info(f"Features file size: {features_size:.2f} MB")
    logger.info(f"Metadata file size: {metadata_size:.2f} MB")

def load_and_reduce_data(
    synthetic: bool = False,
    benign_cap: int = None,
    attack_cap: int = None,
    seed: int = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load data and apply reduction.

    Args:
        synthetic: Whether to use synthetic data
        benign_cap: Maximum number of BENIGN samples to keep
        attack_cap: Maximum number of samples per attack class to keep
        seed: Random seed for reproducibility

    Returns:
        Tuple of (reduced_features_df, reduced_metadata_df)
    """
    # Load data
    if synthetic:
        features_df, metadata_df = load_data(synthetic=True)
    else:
        features_df, metadata_df = load_traffic_labelling_data()

    # Apply reduction
    reduced_features_df, reduced_metadata_df = reduce_dataset(
        features_df, metadata_df, benign_cap, attack_cap, seed
    )

    return reduced_features_df, reduced_metadata_df

def load_traffic_labelling_data(raw_dir: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load TrafficLabelling CSV files, split features and metadata.

    Args:
        raw_dir: Directory containing raw data. If None, uses config.

    Returns:
        Tuple of (features_df, metadata_df)
    """
    # Import here to avoid circular imports
    from src.cyberagent.data_loader import load_traffic_labelling_data as load_tl_data
    return load_tl_data(raw_dir)

if __name__ == "__main__":
    # Check if we want to run the synthetic test or the real reduction
    if len(sys.argv) > 1 and sys.argv[1] == "--synthetic":
        # Test the dataset reduction with synthetic data
        logger.info("Testing dataset reduction with synthetic data...")

        # Test with synthetic data
        logger.info("Loading synthetic data...")
        features, metadata = load_data(synthetic=True)
        logger.info(f"Original synthetic features shape: {features.shape}")
        logger.info(f"Original synthetic metadata shape: {metadata.shape}")

        # Apply reduction with small caps for testing
        reduced_features, reduced_metadata = reduce_dataset(
            features, metadata,
            benign_cap=100,
            attack_cap=50,
            seed=42
        )

        logger.info(f"Reduced synthetic features shape: {reduced_features.shape}")
        logger.info(f"Reduced synthetic metadata shape: {reduced_metadata.shape}")

        # Test saving
        logger.info("Testing save functionality...")
        save_reduced_dataset(
            reduced_features,
            reduced_metadata,
            features_path="data/reduced_test_features.parquet",
            metadata_path="data/reduced_test_metadata.parquet"
        )

        logger.info("Dataset reduction test complete!")
    else:
        # Run the real reduction
        logger.info("Running dataset reduction on real data...")

        # Load real data
        features, metadata = load_traffic_labelling_data()
        logger.info(f"Original real features shape: {features.shape}")
        logger.info(f"Original real metadata shape: {metadata.shape}")

        # Apply reduction with caps from config
        reduced_features, reduced_metadata = reduce_dataset(
            features, metadata,
            benign_cap=config.get("reduction.benign_cap", 300000),
            attack_cap=config.get("reduction.attack_cap", 50000),
            seed=config.get("reduction.seed", config.get("seed", 42))
        )

        logger.info(f"Reduced real features shape: {reduced_features.shape}")
        logger.info(f"Reduced real metadata shape: {reduced_metadata.shape}")

        # Save the reduced dataset
        logger.info("Saving reduced dataset...")
        save_reduced_dataset(reduced_features, reduced_metadata)

        logger.info("Dataset reduction complete!")