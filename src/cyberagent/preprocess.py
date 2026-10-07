"""
Preprocessing module for CyberAgent.
Handles loading, cleaning, splitting, and basic preprocessing of the dataset.
"""
import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from src.cyberagent.config import config
from src.cyberagent.logging_setup import logger

def load_reduced_data(
    features_path: Optional[str] = None,
    metadata_path: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load reduced dataset from Parquet files.

    Args:
        features_path: Path to features Parquet file. If None, uses config.
        metadata_path: Path to metadata Parquet file. If None, uses config.

    Returns:
        Tuple of (features_df, metadata_df)
    """
    if features_path is None:
        features_path = config.get("dataset.processed_dir") + "/flows_features.parquet"
    if metadata_path is None:
        metadata_path = config.get("dataset.processed_dir") + "/flows_meta.parquet"

    features_path = Path(features_path)
    metadata_path = Path(metadata_path)

    if not features_path.exists():
        raise FileNotFoundError(f"Features file not found: {features_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    logger.info(f"Loading features from {features_path}")
    features_df = pd.read_parquet(features_path)

    logger.info(f"Loading metadata from {metadata_path}")
    metadata_df = pd.read_parquet(metadata_path)

    # Ensure flow_id is present in both
    if 'flow_id' not in features_df.columns:
        raise ValueError("flow_id column missing in features_df")
    if 'flow_id' not in metadata_df.columns:
        raise ValueError("flow_id column missing in metadata_df")

    return features_df, metadata_df

def clean_data(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    handle_impossible_negatives: bool = True,
    drop_constant_columns: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Clean the dataset by:
    - Handling impossible negatives (set to NaN)
    - Dropping constant columns
    - Removing duplicate rows (excluding flow_id and Label from duplicate check)
    - After feature dedupe, filter metadata to keep only rows with flow_id present in features.
    - Note: Duplicate row removal is done in dataset reduction, but we can do it again if needed.

    Args:
        features_df: DataFrame with features
        metadata_df: DataFrame with metadata
        handle_impossible_negatives: Whether to replace impossible negatives with NaN
        drop_constant_columns: Whether to drop constant columns

    Returns:
        Tuple of (cleaned_features_df, cleaned_metadata_df)
    """
    logger.info("Starting data cleaning...")

    # Make copies to avoid modifying originals
    features_clean = features_df.copy()
    metadata_clean = metadata_df.copy()

    # Handle impossible negatives in features
    if handle_impossible_negatives:
        # Define impossible negative features (based on domain knowledge)
        impossible_neg_features = [
            'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
            'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
            'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean',
            'Fwd Packet Length Std', 'Bwd Packet Length Max', 'Bwd Packet Length Min',
            'Bwd Packet Length Mean', 'Bwd Packet Length Std', 'Flow Bytes/s',
            'Flow Packets/s', 'Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max',
            'Flow IAT Min', 'Fwd IAT Total', 'Fwd IAT Mean', 'Fwd IAT Std',
            'Fwd IAT Max', 'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean',
            'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags',
            'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags', 'Fwd Header Length',
            'Bwd Header Length', 'Fwd Packets/s', 'Bwd Packets/s',
            'Min Packet Length', 'Max Packet Length', 'Packet Length Mean',
            'Packet Length Std', 'Packet Length Variance', 'FIN Flag Count',
            'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
            'ACK Flag Count', 'URG Flag Count', 'CWE Flag Count',
            'ECE Flag Count', 'Down/Up Ratio', 'Average Packet Size',
            'Avg Fwd Segment Size', 'Avg Bwd Segment Size'
        ]

        # Filter to only those that exist in the dataframe
        existing_neg_features = [f for f in impossible_neg_features if f in features_clean.columns]

        for feat in existing_neg_features:
            # Replace negative values with NaN
            neg_count = (features_clean[feat] < 0).sum()
            if neg_count > 0:
                logger.warning(f"Feature {feat} has {neg_count} negative values. Setting to NaN.")
                features_clean.loc[features_clean[feat] < 0, feat] = np.nan

    # Drop duplicate rows (keeping first occurrence)
    # Exclude flow_id and Label from duplicate check as they may legitimately differ
    duplicate_check_cols = [col for col in features_clean.columns if col not in ['flow_id', 'Label']]
    duplicate_mask = features_clean.duplicated(subset=duplicate_check_cols, keep='first')
    duplicate_count = duplicate_mask.sum()
    if duplicate_count > 0:
        logger.warning(f"Found {duplicate_count} duplicate feature rows. Removing duplicates.")
        # Log duplicates per class if Label column exists
        if 'Label' in features_clean.columns:
            dup_labels = features_clean.loc[duplicate_mask, 'Label']
            dup_counts = dup_labels.value_counts()
            logger.warning(f"Duplicate count per class:\n{dup_counts}")
        features_clean = features_clean[~duplicate_mask].reset_index(drop=True)

    # Drop constant columns
    if drop_constant_columns:
        constant_cols = []
        for col in features_clean.columns:
            # Skip flow_id and Label if present (though Label should not be in features at this stage)
            if col in ['flow_id', 'Label']:
                continue
            # Check if column is constant (all values the same, ignoring NaN)
            if features_clean[col].nunique(dropna=False) == 1:
                constant_cols.append(col)

        if constant_cols:
            logger.warning(f"Dropping constant columns: {constant_cols}")
            features_clean = features_clean.drop(columns=constant_cols)

    # After feature dedupe, filter metadata to keep only rows with flow_id present in features
    # This ensures features and metadata have matching flow_id sets.
    if 'flow_id' in features_clean.columns and 'flow_id' in metadata_clean.columns:
        # Get the set of flow_ids present in features
        feature_flow_ids = set(features_clean['flow_id'])
        # Filter metadata to keep only those flow_ids
        metadata_clean = metadata_clean[metadata_clean['flow_id'].isin(feature_flow_ids)].reset_index(drop=True)
        logger.info(f"After syncing metadata to feature flow_ids: metadata shape {metadata_clean.shape}")

    logger.info(f"Data cleaning complete. Features shape: {features_clean.shape}")

    return features_clean, metadata_clean
def apply_label_grouping(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    label_mapping_config: Optional[Dict[str, str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """
    Apply label grouping based on config.

    Args:
        features_df: DataFrame with features (should have Label column after merge)
        metadata_df: DataFrame with metadata
        label_mapping_config: Dictionary mapping original labels to new labels.
                              If None, uses config or defaults to no grouping.

    Returns:
        Tuple of (features_df_with_label, metadata_df, label_mapping_used)
    """
    logger.info("Applying label grouping...")

    # If Label is not in features_df, merge from metadata_df
    if 'Label' not in features_df.columns:
        # Merge Label from metadata_df using flow_id
        features_df = features_df.merge(
            metadata_df[['flow_id', 'Label']],
            on='flow_id',
            how='left'
        )

    # Get label mapping from config if not provided
    if label_mapping_config is None:
        label_mapping_config = config.get("preprocessing.label_groups", {})

    # If no mapping provided, use identity mapping
    if not label_mapping_config:
        # Create identity mapping for all unique labels
        unique_labels = features_df['Label'].unique()
        label_mapping_config = {label: label for label in unique_labels}
        logger.info("No label grouping configured. Using identity mapping.")
    else:
        logger.info(f"Applying label grouping: {label_mapping_config}")

    # First, normalize labels by replacing corrupted dash character
    # The \x96 character appears as "Web Attack \x96 Brute Force" etc.
    # Replace with proper dash: "Web Attack - Brute Force"
