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
        label_mapping_config = config.get("preprocessing.label_grouping", {})

    # If no mapping provided, use identity mapping
    if not label_mapping_config:
        # Create identity mapping for all unique labels
        unique_labels = features_df['Label'].unique()
        label_mapping_config = {label: label for label in unique_labels}
        logger.info("No label grouping configured. Using identity mapping.")
    else:
        logger.info(f"Applying label grouping: {label_mapping_config}")

    # Apply mapping
    def map_label(label):
        if pd.isna(label):
            return label
        return label_mapping_config.get(label, label)  # If not in mapping, keep original

    features_df['Label'] = features_df['Label'].apply(map_label)

    # Also update metadata_df if it has Label column (for consistency)
    if 'Label' in metadata_df.columns:
        metadata_df['Label'] = metadata_df['Label'].apply(map_label)

    # Save label mapping to results/tables/
    results_dir = Path("results/tables")
    results_dir.mkdir(parents=True, exist_ok=True)
    label_mapping_df = pd.DataFrame(
        list(label_mapping_config.items()),
        columns=['Original_Label', 'Mapped_Label']
    )
    label_mapping_path = results_dir / "label_mapping.csv"
    label_mapping_df.to_csv(label_mapping_path, index=False)
    logger.info(f"Saved label mapping to {label_mapping_path}")

    return features_df, metadata_df, label_mapping_config

def split_data(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    split_mode: Optional[str] = None,
    train_ratio: Optional[float] = None,
    val_ratio: Optional[float] = None,
    test_ratio: Optional[float] = None,
    seed: Optional[int] = None
) -> Tuple[
    pd.DataFrame, pd.DataFrame,  # X_train, X_val, X_test (features)
    pd.DataFrame, pd.DataFrame,  # y_train, y_val, y_test (labels)
    pd.DataFrame, pd.DataFrame,  # train_metadata, val_metadata, test_metadata
]:
    """
    Split data into train, validation, and test sets.

    Args:
        features_df: DataFrame with features and Label column
        metadata_df: DataFrame with metadata
        split_mode: Either "stratified" or "time_aware". If None, uses config.
        train_ratio: Proportion for training set. If None, uses config.
        val_ratio: Proportion for validation set. If None, uses config.
        test_ratio: Proportion for test set. If None, uses config.
        seed: Random seed. If None, uses config.

    Returns:
        Tuple of (X_train, X_val, X_test, y_train, y_val, y_test,
                  train_metadata, val_metadata, test_metadata)
    """
    if split_mode is None:
        split_mode = config.get("split.mode", "stratified")
    if train_ratio is None:
        train_ratio = config.get("split.train_ratio", 0.7)
    if val_ratio is None:
        val_ratio = config.get("split.val_ratio", 0.15)
    if test_ratio is None:
        test_ratio = config.get("split.test_ratio", 0.15)
    if seed is None:
        seed = config.get("split.seed", config.get("seed", 42))

    # Ensure ratios sum to 1
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {total}")

    logger.info(f"Splitting data using {split_mode} mode with seed {seed}")
    logger.info(f"Ratios - train: {train_ratio}, val: {val_ratio}, test: {test_ratio}")

    # Ensure Label column is in features_df
    if 'Label' not in features_df.columns:
        raise ValueError("Label column not found in features_df. Please run apply_label_grouping first.")

    # Separate features and labels
    X = features_df.drop(columns=['Label'])
    y = features_df['Label']

    # First split: train+val vs test
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=test_ratio,
        random_state=seed,
        stratify=y if split_mode == "stratified" else None
    )

    # Second split: train vs val
    # Calculate validation ratio relative to the remaining data
    val_ratio_adjusted = val_ratio / (train_ratio + val_ratio)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_ratio_adjusted,
        random_state=seed,
        stratify=y_temp if split_mode == "stratified" else None
    )

    # Get the corresponding metadata using indices
    # We need to map the indices from the splits back to the original indices.
    # Since we reset the index of X and y after each split, we cannot directly use the indices.
    # Instead, we will use the fact that the order of rows is preserved in the splits.
    # We will create an index array for the original X and y, and then use the indices from the splits to select the metadata.

    # Create an index array for the original X and y
    original_index = np.arange(len(X))

    # Split the index array in the same way as X and y
    index_temp, index_test = train_test_split(
        original_index,
        test_size=test_ratio,
        random_state=seed,
        stratify=y if split_mode == "stratified" else None
    )
    index_train, index_val = train_test_split(
        index_temp,
        test_size=val_ratio_adjusted,
        random_state=seed,
        stratify=y_temp if split_mode == "stratified" else None
    )

    # Now we can use these indices to select the metadata
    train_metadata = metadata_df.iloc[index_train].reset_index(drop=True)
    val_metadata = metadata_df.iloc[index_val].reset_index(drop=True)
    test_metadata = metadata_df.iloc[index_test].reset_index(drop=True)

    # Also reset indices for X and y dataframes
    X_train = X_train.reset_index(drop=True)
    X_val = X_val.reset_index(drop=True)
    X_test = X_test.reset_index(drop=True)
    y_train = y_train.reset_index(drop=True)
    y_val = y_val.reset_index(drop=True)
    y_test = y_test.reset_index(drop=True)

    logger.info(f"Train set: {len(X_train)} samples")
    logger.info(f"Validation set: {len(X_val)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Log class distribution in each set
    logger.info(f"Train label distribution:\n{y_train.value_counts()}")
    logger.info(f"Validation label distribution:\n{y_val.value_counts()}")
    logger.info(f"Test label distribution:\n{y_test.value_counts()}")

    return (
        X_train, X_val, X_test,
        y_train, y_val, y_test,
        train_metadata, val_metadata, test_metadata
    )

def preprocess_train_fit(
    X_train: pd.DataFrame,
    correlation_threshold: Optional[float] = None,
    feature_selection_method: Optional[str] = None,
    top_k_features: Optional[int] = None
) -> Tuple[
    SimpleImputer, StandardScaler,
    Optional[np.ndarray],  # Features to keep after correlation drop
    Optional[np.ndarray]   # Features to keep after selection
]:
    """
    Fit preprocessing steps on training data only.

    Args:
        X_train: Training features DataFrame
        correlation_threshold: Threshold for dropping correlated features. If None, uses config.
        feature_selection_method: Method for feature selection. If None, uses config.
        top_k_features: Number of top features to select. If None, uses config.

    Returns:
        Tuple of (imputer, scaler, correlation_mask, selection_mask)
        where masks are boolean arrays indicating which features to keep.
    """
    if correlation_threshold is None:
        correlation_threshold = config.get("preprocessing.correlation_threshold", 0.95)
    if feature_selection_method is None:
        feature_selection_method = config.get("preprocessing.feature_selection_method", "mutual_info")
    if top_k_features is None:
        top_k_features = config.get("preprocessing.top_k_features", 50)

    logger.info("Fitting preprocessing steps on training data...")

    # Step 1: Imputer (median)
    imputer = SimpleImputer(strategy='median')
    imputer.fit(X_train)
    X_train_imputed = imputer.transform(X_train)

    # Step 2: Scaler (StandardScaler)
    scaler = StandardScaler()
    scaler.fit(X_train_imputed)

    # Step 3: Correlation-based feature drop
    # Compute correlation matrix on imputed and scaled data
    X_train_scaled = scaler.transform(X_train_imputed)
    corr_matrix = np.corrcoef(X_train_scaled, rowvar=False)

    # Create mask for features to keep (True = keep)
    # We'll keep one feature from each pair of highly correlated features
    correlation_mask = np.ones(X_train.shape[1], dtype=bool)
    for i in range(X_train.shape[1]):
        for j in range(i+1, X_train.shape[1]):
            # Check for high absolute correlation or NaN (which occurs when at least one feature is constant)
            if np.isnan(corr_matrix[i, j]) or abs(corr_matrix[i, j]) > correlation_threshold:
                # If both are still marked to keep, drop the one with higher index (arbitrary)
                if correlation_mask[i] and correlation_mask[j]:
                    correlation_mask[j] = False

    logger.info(f"Correlation drop: keeping {np.sum(correlation_mask)} of {X_train.shape[1]} features")

    # Step 4: Feature selection
    # For simplicity, we'll use variance threshold if method is not recognized
    # In a full implementation, we would use mutual_info or tree importance
    selection_mask = correlation_mask.copy()  # Start with correlation mask

    if feature_selection_method == "variance":
        from sklearn.feature_selection import VarianceThreshold
        selector = VarianceThreshold()
        # Apply to data that has already been imputed and scaled, and correlation dropped
        X_temp = X_train_scaled[:, correlation_mask]
        selector.fit(X_temp)
        # Get indices of selected features within the correlation_mask subset
        selected_within_corr = selector.get_support()
        # Map back to original feature indices
        # We'll create a temporary array to map
        temp_index = 0
        for i in range(len(selection_mask)):
            if correlation_mask[i]:
                if not selected_within_corr[temp_index]:
                    selection_mask[i] = False
                temp_index += 1
        logger.info(f"Variance threshold: keeping {np.sum(selection_mask)} features")
    elif feature_selection_method == "mutual_info":
        # For mutual info, we need discrete labels. We'll skip for now and use variance as placeholder
        logger.warning("Mutual information selection not implemented. Using variance threshold.")
        from sklearn.feature_selection import VarianceThreshold
        selector = VarianceThreshold()
        X_temp = X_train_scaled[:, correlation_mask]
        selector.fit(X_temp)
        selected_within_corr = selector.get_support()
        temp_index = 0
        for i in range(len(selection_mask)):
            if correlation_mask[i]:
                if not selected_within_corr[temp_index]:
                    selection_mask[i] = False
                temp_index += 1
    elif feature_selection_method == "tree_importance":
        # For tree importance, we need a model. We'll skip for now and use variance as placeholder
        logger.warning("Tree importance selection not implemented. Using variance threshold.")
        from sklearn.feature_selection import VarianceThreshold
        selector = VarianceThreshold()
        X_temp = X_train_scaled[:, correlation_mask]
        selector.fit(X_temp)
        selected_within_corr = selector.get_support()
        temp_index = 0
        for i in range(len(selection_mask)):
            if correlation_mask[i]:
                if not selected_within_corr[temp_index]:
                    selection_mask[i] = False
                temp_index += 1
    else:
        logger.warning(f"Unknown feature selection method: {feature_selection_method}. Skipping selection.")

    # Apply top_k if specified and we have more features than top_k
    if top_k_features is not None and np.sum(selection_mask) > top_k_features:
        # Select top k features based on variance (as a simple proxy)
        from sklearn.feature_selection import VarianceThreshold
        selector = VarianceThreshold()
        # We'll fit on the data that has passed correlation drop
        X_temp = X_train_scaled[:, selection_mask]
        selector.fit(X_temp)
        variances = selector.variances_
        # Get indices of top k variances
        top_k_indices = np.argsort(variances)[-top_k_features:]
        # Create a new mask for selection
        new_selection_mask = np.zeros_like(selection_mask, dtype=bool)
        # Map top_k_indices back to original feature indices via selection_mask
        selected_count = 0
        for i in range(len(selection_mask)):
            if selection_mask[i]:
                if selected_count in top_k_indices:
                    new_selection_mask[i] = True
                selected_count += 1
        selection_mask = new_selection_mask
        logger.info(f"Top-K selection: keeping {top_k_features} features")

    logger.info(f"Feature selection complete: keeping {np.sum(selection_mask)} features")

    return imputer, scaler, correlation_mask, selection_mask

def preprocess_transform(
    X: pd.DataFrame,
    imputer: SimpleImputer,
    scaler: StandardScaler,
    correlation_mask: np.ndarray,
    selection_mask: np.ndarray
) -> pd.DataFrame:
    """
    Transform data using fitted preprocessors.

    Args:
        X: Features DataFrame to transform
        imputer: Fitted imputer
        scaler: Fitted scaler
        correlation_mask: Boolean mask for correlation drop
        selection_mask: Boolean mask for feature selection

    Returns:
        Transformed features DataFrame
    """
    # Step 1: Impute
    X_imputed = imputer.transform(X)

    # Step 2: Scale
    X_scaled = scaler.transform(X_imputed)

    # Step 3: Apply correlation mask
    X_corr = X_scaled[:, correlation_mask]

    # Step 4: Apply selection mask
    X_selected = X_corr[:, selection_mask]

    # Get feature names after selection
    # We need to track which original features are kept
    # For simplicity, we'll return a DataFrame with generic column names
    # In a full implementation, we would keep track of feature names
    feature_names = [f"feature_{i}" for i in range(X_selected.shape[1])]
    X_transformed = pd.DataFrame(X_selected, columns=feature_names)

    return X_transformed

def handle_imbalance(
    y_train: pd.Series,
    method: Optional[str] = None
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Handle class imbalance in training labels.

    Args:
        y_train: Training labels
        method: Either "class_weight" or "smote". If None, uses config.

    Returns:
        Tuple of (processed_y_train, info_dict)
        where info_dict contains information about the handling (e.g., class weights)
    """
    if method is None:
        method = config.get("imbalance.method", "class_weight")

    logger.info(f"Handling imbalance using method: {method}")

    info = {}

    if method == "class_weight":
        # Compute class weights
        from sklearn.utils.class_weight import compute_class_weight
        classes = np.unique(y_train)
        class_weights = compute_class_weight(
            class_weight='balanced',
            classes=classes,
            y=y_train
        )
        class_weight_dict = dict(zip(classes, class_weights))
        info['class_weight'] = class_weight_dict
        logger.info(f"Computed class weights: {class_weight_dict}")
        # Return y_train unchanged (class weight is used in model fitting)
        return y_train, info

    elif method == "smote":
        # Apply SMOTE
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(random_state=config.get("seed", 42))
            # We need to return both X and y, but this function only handles y.
            # In practice, SMOTE is applied to X and y together.
            # We'll return a flag indicating that SMOTE should be applied to X and y together.
            info['apply_smote'] = True
            logger.info("SMOTE will be applied to features and labels together.")
            # Return y_train unchanged (SMOTE will return new y)
            return y_train, info
        except ImportError:
            logger.warning("imbalanced-learn not installed. Falling back to class_weight.")
            return handle_imbalance(y_train, method="class_weight")

    else:
        logger.warning(f"Unknown imbalance method: {method}. No action taken.")
        return y_train, info

# Example usage function for demonstration
def example_preprocessing_pipeline():
    """
    Example of how to use the preprocessing functions.
    This is for demonstration and testing.
    """
    logger.info("Running example preprocessing pipeline...")

    # In a real scenario, you would load reduced data
    # For this example, we'll use synthetic data from the data_loader
    from src.cyberagent.data_loader import load_data
    from scripts.reduce_dataset import reduce_dataset

    # Load synthetic data
    features, metadata = load_data(synthetic=True)
    logger.info(f"Loaded synthetic data: {features.shape} features, {metadata.shape} metadata")

    # Reduce dataset (small caps for example)
    features_reduced, metadata_reduced = reduce_dataset(
        features, metadata,
        benign_cap=100,
        attack_cap=50,
        seed=42
    )

    # Clean data
    features_clean, metadata_clean = clean_data(
        features_reduced, metadata_reduced,
        handle_impossible_negatives=True,
        drop_constant_columns=True
    )

    # Apply label grouping (using default identity mapping)
    features_labeled, metadata_labeled, label_map = apply_label_grouping(
        features_clean, metadata_clean
    )

    # Split data
    (X_train, X_val, X_test,
     y_train, y_val, y_test,
     train_meta, val_meta, test_meta) = split_data(
        features_labeled, metadata_labeled,
        split_mode="stratified",
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        seed=42
    )

    # Fit preprocessors on training data
    imputer, scaler, corr_mask, sel_mask = preprocess_train_fit(
        X_train,
        correlation_threshold=0.95,
        feature_selection_method="variance",
        top_k_features=20
    )

    # Transform all sets
    X_train_transformed = preprocess_transform(X_train, imputer, scaler, corr_mask, sel_mask)
    X_val_transformed = preprocess_transform(X_val, imputer, scaler, corr_mask, sel_mask)
    X_test_transformed = preprocess_transform(X_test, imputer, scaler, corr_mask, sel_mask)

    logger.info(f"Transformed train shape: {X_train_transformed.shape}")
    logger.info(f"Transformed val shape: {X_val_transformed.shape}")
    logger.info(f"Transformed test shape: {X_test_transformed.shape}")

    # Handle imbalance (class weight example)
    y_train_processed, imbalance_info = handle_imbalance(y_train, method="class_weight")

    logger.info("Example preprocessing pipeline complete.")

    return {
        'X_train': X_train_transformed,
        'X_val': X_val_transformed,
        'X_test': X_test_transformed,
        'y_train': y_train_processed,
        'y_val': y_val,
        'y_test': y_test,
        'train_metadata': train_meta,
        'val_metadata': val_meta,
        'test_metadata': test_meta,
        'imbalance_info': imbalance_info,
        'label_mapping': label_map
    }

if __name__ == "__main__":
    # Run example pipeline when script is executed directly
    example_preprocessing_pipeline()