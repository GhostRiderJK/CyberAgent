"""
Preprocessing module for CyberAgent.
Handles loading, cleaning, splitting, and basic preprocessing of the dataset.
"""
import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import VarianceThreshold, mutual_info_classif
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

    # Handle duplicate rows
    # Exclude flow_id and Label from duplicate check as they may legitimately differ
    duplicate_check_cols = [col for col in features_clean.columns if col not in ['flow_id', 'Label']]

    if len(duplicate_check_cols) > 0:
        # Find all duplicate rows (marked as True for all duplicates of each group)
        duplicate_mask_all = features_clean.duplicated(subset=duplicate_check_cols, keep=False)
        duplicate_count = duplicate_mask_all.sum()

        if duplicate_count > 0:
            logger.warning(f"Found {duplicate_count} duplicate feature rows.")

            # Get the duplicate rows
            duplicate_rows = features_clean[duplicate_mask_all].copy()

            # Group by feature columns to analyze label distribution within each group
            if 'Label' in features_clean.columns:
                # Group duplicate rows by their feature values
                duplicate_groups = duplicate_rows.groupby(duplicate_check_cols)

                cross_label_groups = []
                same_label_groups = []

                for group_key, group_df in duplicate_groups:
                    unique_labels = group_df['Label'].unique()
                    if len(unique_labels) > 1:
                        cross_label_groups.append((group_key, group_df))
                    else:
                        same_label_groups.append((group_key, group_df))

                cross_label_row_count = sum(len(group_df) for _, group_df in cross_label_groups)
                same_label_row_count = sum(len(group_df) for _, group_df in same_label_groups)
                total_rows = len(features_clean)

                cross_label_percentage = (cross_label_row_count / total_rows) * 100

                logger.info(f"Duplicate analysis: {len(cross_label_groups)} cross-label groups ({cross_label_row_count} rows, {cross_label_percentage:.4f}%), "
                            f"{len(same_label_groups)} same-label groups ({same_label_row_count} rows)")

                # Apply the cross-label duplicate handling rule
                if cross_label_percentage < 0.5:
                    # Drop ALL rows in cross-label groups
                    cross_label_indices = []
                    for _, group_df in cross_label_groups:
                        cross_label_indices.extend(group_df.index.tolist())

                    # For same-label groups, keep exactly one row per group (first occurrence)
                    same_label_indices_to_keep = []
                    for _, group_df in same_label_groups:
                        # Keep the first occurrence of each same-label group
                        same_label_indices_to_keep.append(group_df.index[0])

                    # Create mask for rows to keep:
                    # - All non-duplicate rows
                    # - One row per same-label duplicate group
                    # - No rows from cross-label duplicate groups
                    non_duplicate_mask = ~duplicate_mask_all
                    same_label_keep_mask = pd.Series(False, index=features_clean.index)
                    same_label_keep_mask[same_label_indices_to_keep] = True

                    rows_to_keep_mask = non_duplicate_mask | same_label_keep_mask
                    features_clean = features_clean[rows_to_keep_mask].reset_index(drop=True)

                    logger.info(f"Dropped {cross_label_row_count} cross-label duplicate rows and "
                                f"{same_label_row_count - len(same_label_indices_to_keep)} same-label duplicate rows "
                                f"(kept {len(same_label_indices_to_keep)} rows from same-label groups).")
                else:
                    # Cross-label rows >= 0.5%, make no change and stop for decision
                    logger.warning(f"Cross-label duplicate rows ({cross_label_percentage:.4f}%) >= 0.5%. "
                                   "No changes made to duplicate handling. Manual review required.")
                    # Make truly no changes to the data - do not remove any duplicates
                    pass
            else:
                # No Label column, use original duplicate handling
                logger.warning("Label column not found, using standard duplicate removal.")
                duplicate_mask = features_clean.duplicated(subset=duplicate_check_cols, keep='first')
                features_clean = features_clean[~duplicate_mask].reset_index(drop=True)
        else:
            logger.info("No duplicate feature rows found.")
    else:
        logger.warning("No feature columns available for duplicate checking.")

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

    # Get label mapping from config if not provided (None means use config)
    if label_mapping_config is None:
        label_mapping_config = config.get("preprocessing.label_groups", {})

    # First, normalize labels by replacing corrupted dash character
    # The \x96 character appears as "Web Attack \x96 Brute Force" etc.
    # Replace with proper dash: "Web Attack - Brute Force"
    if 'Label' in features_df.columns:
        features_df['Label'] = features_df['Label'].astype(str).apply(
            lambda x: re.sub(r'[‐-―−﹘﹣－]', '-', x.strip())
        )

    # Handle label mapping:
    # - If label_mapping_config is None (handled above), we got it from config
    # - If label_mapping_config is {} (empty dict), return identity mapping over labels present
    # - If label_mapping_config has values, use that mapping
    if label_mapping_config == {}:
        # Create identity mapping for all unique labels
        unique_labels = features_df['Label'].unique()
        label_mapping_config = {label: label for label in unique_labels}
        logger.info("Empty label mapping provided. Using identity mapping.")
    elif not label_mapping_config:
        # This case shouldn't happen now that we distinguish None and {},
        # but keep it for safety (handles other falsy values like False)
        unique_labels = features_df['Label'].unique()
        label_mapping_config = {label: label for label in unique_labels}
        logger.info("No label grouping configured. Using identity mapping.")
    else:
        logger.info(f"Applying label grouping: {label_mapping_config}")

    # Apply label mapping if provided (after identity handling)
    if label_mapping_config:
        features_df['Label'] = features_df['Label'].map(label_mapping_config).fillna(features_df['Label'])
        logger.info(f"Applied label mapping: {label_mapping_config}")

    # Additionally, ensure any label starting with "Web Attack" is mapped to "Web Attack"
    # This catches any Web Attack variants not explicitly listed in the mapping.
    if 'Label' in features_df.columns:
        web_attack_mask = features_df['Label'].str.startswith('Web Attack')
        features_df.loc[web_attack_mask, 'Label'] = 'Web Attack'

    return features_df, metadata_df, label_mapping_config

def split_data(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    split_mode: str = "stratified",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42
) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame,
    pd.Series, pd.Series, pd.Series,
    pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """
    Split data into training, validation, and test sets.

    Args:
        features_df: DataFrame with features (should include Label column for stratification)
        metadata_df: DataFrame with metadata
        split_mode: Either "stratified" or "time_aware"
        train_ratio: Proportion of data for training
        val_ratio: Proportion of data for validation
        test_ratio: Proportion of data for testing
        seed: Random seed

    Returns:
        Tuple of (X_train, X_val, X_test, y_train, y_val, y_test, train_meta, val_meta, test_meta)
    """
    if not np.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError("Split ratios must sum to 1.0")

    # Get indices
    indices = np.arange(len(features_df))

    if split_mode == "stratified":
        # Stratify by Label if present, otherwise no stratification
        if 'Label' in features_df.columns:
            stratify = features_df['Label']
            stratify_array = stratify.values
        else:
            stratify = None
            stratify_array = None
    else:
        # For time_aware, we assume the data is already sorted by time
        stratify = None
        stratify_array = None

    # Split into train and temp (val + test)
    train_indices, temp_indices = train_test_split(
        indices,
        train_size=train_ratio,
        random_state=seed,
        stratify=stratify_array
    )

    # Split temp into val and test
    val_size = val_ratio / (val_ratio + test_ratio)
    temp_stratify = stratify_array[temp_indices] if stratify_array is not None else None
    val_indices, test_indices = train_test_split(
        temp_indices,
        train_size=val_size,
        random_state=seed,
        stratify=temp_stratify
    )

    # Extract data for each split
    def _extract_split(idx):
        X = features_df.loc[idx].drop(columns=['flow_id', 'Label']) if 'Label' in features_df.columns else features_df.loc[idx].drop(columns=['flow_id'])
        y = features_df.loc[idx]['Label'] if 'Label' in features_df.columns else pd.Series(dtype=object)
        meta = metadata_df.loc[idx]
        return X, y, meta

    X_train, y_train, train_meta = _extract_split(train_indices)
    X_val, y_val, val_meta = _extract_split(val_indices)
    X_test, y_test, test_meta = _extract_split(test_indices)

    return X_train, X_val, X_test, y_train, y_val, y_test, train_meta, val_meta, test_meta

def preprocess_train_fit(
    X_train: pd.DataFrame,
    correlation_threshold: float = 0.95,
    feature_selection_method: str = "variance",
    top_k_features: int = 50
) -> Tuple[SimpleImputer, StandardScaler, np.ndarray]:
    """
    Fit preprocessing steps on training data.

    Args:
        X_train: Training features DataFrame
        correlation_threshold: Threshold for correlation pruning
        feature_selection_method: Method for feature selection ("variance" or "mutual_info")
        top_k_features: Number of top features to select

    Returns:
        Tuple of (imputer, scaler, feature_mask) where feature_mask is a boolean array
        indicating which features to keep after correlation pruning and selection.
    """
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    # Replace infinities with NaN before imputation
    X_train_replaced = X_train.replace([np.inf, -np.inf], np.nan)
    # Imputer
    imputer = SimpleImputer(strategy='median')
    imputer.fit(X_train_replaced)
    X_imputed = imputer.transform(X_train_replaced)

    # Scaler
    scaler = StandardScaler()
    scaler.fit(X_imputed)
    X_scaled = scaler.transform(X_imputed)

    # Correlation mask
    corr_df = pd.DataFrame(X_scaled, columns=X_train.columns)
    corr_matrix = corr_df.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [column for column in upper.columns if any(upper[column] > correlation_threshold)]
    correlation_mask = np.array([col not in to_drop for col in X_train.columns])

    # Selection mask
    if feature_selection_method == "variance":
        selector = VarianceThreshold(threshold=0.0)  # Remove zero variance features
        selector.fit(X_scaled[:, correlation_mask])
        # Select top k features by variance
        variances = selector.variances_
        if len(variances) > top_k_features:
            # Get indices of top k variances
            top_indices = np.argsort(variances)[-top_k_features:]
            selection_mask = np.zeros(len(X_train.columns), dtype=bool)
            selection_mask[correlation_mask] = False
            selection_mask[correlation_mask][top_indices] = True
        else:
            selection_mask = np.zeros(len(X_train.columns), dtype=bool)
            selection_mask[correlation_mask] = selector.get_support()
    elif feature_selection_method == "mutual_info":
        # For mutual_info_classif, we need y. We don't have y here.
        # We'll need to pass y to this function or compute it differently.
        # For now, we'll use variance as fallback and log a warning.
        logger.warning("Mutual information feature selection requires y. Falling back to variance.")
        selector = VarianceThreshold(threshold=0.0)  # Remove zero variance features
        selector.fit(X_scaled[:, correlation_mask])
        # Select top k features by variance
        variances = selector.variances_
        if len(variances) > top_k_features:
            # Get indices of top k variances
            top_indices = np.argsort(variances)[-top_k_features:]
            selection_mask = np.zeros(len(X_train.columns), dtype=bool
            )
            selection_mask[correlation_mask] = False
            selection_mask[correlation_mask][top_indices] = True
        else:
            selection_mask = np.zeros(len(X_train.columns), dtype=bool)
            selection_mask[correlation_mask] = selector.get_support()
    else:
        raise ValueError(f"Unknown feature selection method: {feature_selection_method}")

    # Combine masks: keep only if correlation_mask and selection_mask are both True
    feature_mask = correlation_mask & selection_mask
    return imputer, scaler, feature_mask

def preprocess_transform(
    X: pd.DataFrame,
    imputer: SimpleImputer,
    scaler: StandardScaler,
    feature_mask: np.ndarray
) -> pd.DataFrame:
    """
    Transform data using fitted preprocessors.

    Args:
        X: Features DataFrame to transform
        imputer: Fitted SimpleImputer
        scaler: Fitted StandardScaler
        feature_mask: Boolean mask indicating which features to keep

    Returns:
        Transformed features DataFrame
    """
    # Replace infinities with NaN before imputation
    X_replaced = X.replace([np.inf, -np.inf], np.nan)
    X_imputed = imputer.transform(X_replaced)
    X_scaled = scaler.transform(X_imputed)
    X_selected = X_scaled[:, feature_mask]
    # Get the selected feature names
    selected_features = X.columns[feature_mask]
    return pd.DataFrame(X_selected, columns=selected_features, index=X.index)

def handle_imbalance(
    y_train: pd.Series,
    method: str = "class_weight"
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Handle class imbalance.

    Args:
        y_train: Training labels
        method: Method to handle imbalance ("class_weight" or "smote")

    Returns:
        Tuple of (y_train unchanged, info_dict)
    """
    if method == "class_weight":
        from sklearn.utils.class_weight import compute_class_weight
        # Calculate class weights
        class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
        class_weight_dict = dict(zip(np.unique(y_train), class_weights))
        info = {'class_weight': class_weight_dict}
        return y_train, info
    elif method == "smote":
        # TODO: Implement SMOTE
        raise NotImplementedError("SMOTE not implemented yet")
    else:
        raise ValueError(f"Unknown imbalance handling method: {method}")

def example_preprocessing_pipeline() -> Dict[str, Any]:
    """
    Example preprocessing pipeline that loads data, cleans it, applies label grouping,
    splits into train/val/test and holdout, and preprocesses features.

    Returns:
        Dictionary with keys:
            X_train, X_val, X_test: Preprocessed features (DataFrames)
            y_train, y_val, y_test: Labels (Series)
            imbalance_info: Dictionary with class weight information
    """
    from sklearn.utils.class_weight import compute_class_weight

    # Load data
    features_df, metadata_df = load_reduced_data()

    # Apply label grouping
    features_with_label, metadata_with_label, label_mapping = apply_label_grouping(
        features_df, metadata_df
    )

    # Clean data (now that we have Label, we can get per-label dedupe counts)
    features_clean, metadata_clean = clean_data(
        features_with_label, metadata_with_label,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Check that flow_id and Label are not in the features for modeling (they will be removed later)
    # But note: at this point, features_clean still has flow_id and Label.
    # We will remove them when we split.

    # Holdout split: remove zero-day holdout labels from supervised set
    zero_day_holdout_labels = config.get("preprocessing.zero_day_holdout_labels", [])
    supervised_mask = ~features_clean['Label'].isin(zero_day_holdout_labels)
    holdout_mask = features_clean['Label'].isin(zero_day_holdout_labels)

    supervised_features = features_clean[supervised_mask].copy()
    holdout_features = features_clean[holdout_mask].copy()

    # Print holdout label distribution
    if len(holdout_features) > 0:
        holdout_counts = holdout_features['Label'].value_counts()
        logger.info(f"Holdout label distribution:\n{holdout_counts}")
        # Assert holdout set is exactly the zero-day holdout labels
        expected_holdout_set = set(zero_day_holdout_labels)
        actual_holdout_set = set(holdout_features['Label'].unique())
        if actual_holdout_set != expected_holdout_set:
            raise AssertionError(
                f"Holdout set mismatch. Expected: {expected_holdout_set}, Got: {actual_holdout_set}"
            )
    else:
        logger.info("No holdout samples found.")

    # Supervised set: split into train, val, test
    # We will use the split_data function on the supervised set
    # Note: supervised_features has flow_id, features, and Label
    # metadata_clean has flow_id and maybe other columns? We'll use the metadata_clean that corresponds to the supervised set.
    # We need to get the metadata for the supervised set.
    # Since we filtered features_clean, we must also filter metadata_clean by the same flow_ids.
    supervised_flow_ids = set(supervised_features['flow_id'])
    supervised_metadata = metadata_clean[metadata_clean['flow_id'].isin(supervised_flow_ids)].copy()
    holdout_metadata = metadata_clean[metadata_clean['flow_id'].isin(set(holdout_features['flow_id']))].copy()

    # Reset index to avoid indexing issues in split_data
    supervised_features = supervised_features.reset_index(drop=True)
    supervised_metadata = supervised_metadata.reset_index(drop=True)
    holdout_features = holdout_features.reset_index(drop=True)
    holdout_metadata = holdout_metadata.reset_index(drop=True)

    # Split supervised data
    (X_train, X_val, X_test,
     y_train, y_val, y_test,
     train_meta, val_meta, test_meta) = split_data(
        supervised_features,
        supervised_metadata,
        split_mode=config.get("split.mode", "stratified"),
        train_ratio=config.get("split.train_ratio", 0.7),
        val_ratio=config.get("split.val_ratio", 0.15),
        test_ratio=config.get("split.test_ratio", 0.15),
        seed=config.get("split.seed", 42)
    )

    # Assert that flow_id and Label are not in the feature sets
    for df, name in [(X_train, "X_train"), (X_val, "X_val"), (X_test, "X_test")]:
        if 'flow_id' in df.columns:
            raise AssertionError(f"flow_id found in {name}")
        if 'Label' in df.columns:
            raise AssertionError(f"Label found in {name}")

    # Print live value_counts of y_train, y_val, y_test
    logger.info(f"y_train distribution:\n{y_train.value_counts()}")
    logger.info(f"y_val distribution:\n{y_val.value_counts()}")
    logger.info(f"y_test distribution:\n{y_test.value_counts()}")

    # Assert supervised label set állt matches expected
    expected_supervised_set = {
        "BENIGN", "Bot", "DDoS", "DoS GoldenEye", "DoS Hulk",
        "DoS Slowhttptest", "DoS slowloris", "FTP-Patator",
        "PortScan", "SSH-Patator", "Web Attack"
    }
    actual_supervised_set = set(
        pd.concat([y_train, y_val, y_test]).unique()
    )
    if actual_supervised_set != expected_supervised_set:
        raise AssertionError(
            f"Supervised label set mismatch. Expected: {expected_supervised_set}, Got: {actual_supervised_set}"
        )

    # Preprocessing: fit on training data
    correlation_threshold = config.get("preprocessing.correlation_threshold", 0.95)
    feature_selection_method = config.get("preprocessing.feature_selection_method", "mutual_info")
    top_k_features = config.get("preprocessing.top_k_features", 50)

    imputer, scaler, feature_mask = preprocess_train_fit(
        X_train,
        correlation_threshold=correlation_threshold,
        feature_selection_method=feature_selection_method,
        top_k_features=top_k_features
    )

    # Transform all sets
    X_train_processed = preprocess_transform(X_train, imputer, scaler, feature_mask)
    X_val_processed = preprocess_transform(X_val, imputer, scaler, feature_mask)
    X_test_processed = preprocess_transform(X_test, imputer, scaler, feature_mask)

    # Print feature count and column list
    logger.info(f"Number of features after preprocessing: {X_train_processed.shape[1]}")
    logger.info(f"Feature names: {list(X_train_processed.columns)}")

    # Handle imbalance
    y_train_processed, imbalance_info = handle_imbalance(
        y_train,
        method=config.get("imbalance.method", "class_weight")
    )

    # Return processed data
    return {
        'X_train': X_train_processed,
        'X_val': X_val_processed,
        'X_test': X_test_processed,
        'y_train': y_train_processed,
        'y_val': y_val,
        'y_test': y_test,
        'imbalance_info': imbalance_info
    }