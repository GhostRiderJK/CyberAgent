"""
Data loader for CyberAgent.
Handles loading and initial processing of the CIC-IDS2017 dataset.
"""
import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from typing import Tuple, Optional
from .config import config
from .logging_setup import logger

def normalize_label(label: str) -> str:
    """
    Normalize label text by stripping whitespace and fixing corrupted dash characters.

    Args:
        label: Raw label string

    Returns:
        Normalized label string
    """
    if pd.isna(label):
        return label

    # Strip whitespace
    label = str(label).strip()

    # Fix corrupted dash character in Web Attack labels
    # Replace various dash-like characters with standard hyphen
    label = re.sub(r'[‐-―−﹘﹣－]', '-', label)

    return label

def load_traffic_labelling_data(raw_dir: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load TrafficLabelling CSV files, split features and metadata.

    Args:
        raw_dir: Directory containing raw data. If None, uses config.

    Returns:
        Tuple of (features_df, metadata_df)
    """
    if raw_dir is None:
        raw_dir = config.get("dataset.raw_dir")

    primary_folder = config.get("dataset.primary_folder")
    file_extension = config.get("dataset.file_extension")

    data_path = Path(raw_dir) / primary_folder

    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    # Find all CSV files
    csv_files = list(data_path.glob(f"*{file_extension}"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_path} with extension {file_extension}")

    logger.info(f"Found {len(csv_files)} CSV files to load")

    # Load and concatenate all files
    dfs = []
    for file in csv_files:
        logger.info(f"Loading {file.name}")
        try:
            df = pd.read_csv(
                file,
                encoding="latin1",
                low_memory=False
            )
            dfs.append(df)
        except Exception as e:
            logger.error(f"Error loading {file.name}: {e}")
            raise

    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Combined dataset shape: {combined_df.shape}")

    # Strip whitespace from column names
    combined_df.columns = [col.strip() for col in combined_df.columns]

    # Check for and drop duplicate columns that arise from pandas renaming duplicates
    # For example, if a column name appears twice in the CSV, pandas will rename the second to 'col.1'
    # We want to drop the renamed duplicates and keep the base name.
    cols_to_drop = []
    for col in combined_df.columns:
        # Match pattern: base name followed by .<digits> at the end
        match = re.match(r'^(.+)\.\d+$', col)
        if match:
            base_name = match.group(1)
            if base_name in combined_df.columns:
                cols_to_drop.append(col)
                logger.warning(f"Found duplicate column: {col} (base: {base_name})")

    if cols_to_drop:
        combined_df = combined_df.drop(columns=cols_to_drop)
        logger.info(f"After dropping duplicate columns, shape: {combined_df.shape}")

    # Normalize labels
    if 'Label' in combined_df.columns:
        combined_df['Label'] = combined_df['Label'].apply(normalize_label)
        # Save label mapping
        label_mapping = combined_df['Label'].value_counts().reset_index()
        label_mapping.columns = ['Label', 'Count']
        label_mapping_path = Path("results/tables/label_mapping.csv")
        label_mapping_path.parent.mkdir(parents=True, exist_ok=True)
        label_mapping.to_csv(label_mapping_path, index=False)
        logger.info(f"Saved label mapping to {label_mapping_path}")

    # Define metadata columns (kept separate, never used as model features)
    metadata_columns = ['Flow ID', 'Source IP', 'Source Port', 'Destination IP', 'Timestamp']

    # Check which metadata columns exist
    available_metadata_cols = [col for col in metadata_columns if col in combined_df.columns]
    missing_metadata_cols = [col for col in metadata_columns if col not in combined_df.columns]

    if missing_metadata_cols:
        logger.warning(f"Missing metadata columns: {missing_metadata_cols}")

    # Split features and metadata
    if available_metadata_cols:
        metadata_df = combined_df[available_metadata_cols].copy()
        features_df = combined_df.drop(columns=available_metadata_cols)
    else:
        metadata_df = pd.DataFrame()
        features_df = combined_df.copy()

    # Keep Destination Port and Protocol as features (configurable)
    # For now, we keep them as features unless specifically excluded

    # Parse timestamps if they exist
    if 'Timestamp' in metadata_df.columns:
        logger.info("Parsing timestamps...")
        # Timestamps have no AM/PM marker, infer PM for hours 1-7
        def parse_timestamp(ts):
            if pd.isna(ts):
                return ts
            try:
                # Try parsing as is
                return pd.to_datetime(ts, format='%H:%M:%S')
            except:
                try:
                    # Try with date if present
                    return pd.to_datetime(ts)
                except:
                    return pd.NaT

        metadata_df['Timestamp'] = metadata_df['Timestamp'].apply(parse_timestamp)

        # Infer PM for hours 1-7 (working hours 8:00-17:00)
        # This is a simplification - in reality we'd need more context
        def infer_pm(dt):
            if pd.isna(dt):
                return dt
            # If hour is between 1 and 7, assume PM
            if 1 <= dt.hour <= 7:
                return dt.replace(hour=dt.hour + 12)
            return dt

        metadata_df['Timestamp'] = metadata_df['Timestamp'].apply(infer_pm)
        logger.info("Timestamp parsing complete")

    # Create stable integer flow_id (row index in reduced dataset)
    # Note: This will be properly set after dataset reduction
    # For now, we'll use the original index
    features_df['flow_id'] = range(len(features_df))
    if len(metadata_df) > 0:
        metadata_df['flow_id'] = range(len(metadata_df))

    logger.info(f"Features shape: {features_df.shape}")
    logger.info(f"Metadata shape: {metadata_df.shape}")

    return features_df, metadata_df

def load_machinelearningcve_data(raw_dir: str = None) -> pd.DataFrame:
    """
    Load MachineLearningCSV data for cross-check (optional).

    Args:
        raw_dir: Directory containing raw data. If None, uses config.

    Returns:
        DataFrame with MachineLearningCVE data
    """
    if raw_dir is None:
        raw_dir = config.get("dataset.raw_dir")

    secondary_folder = config.get("dataset.secondary_folder")
    file_extension = config.get("dataset.file_extension")

    data_path = Path(raw_dir) / secondary_folder

    if not data_path.exists():
        logger.warning(f"MachineLearningCSV directory not found: {data_path}")
        return pd.DataFrame()

    # Find all CSV files
    csv_files = list(data_path.glob(f"*{file_extension}"))

    if not csv_files:
        logger.warning(f"No CSV files found in {data_path} with extension {file_extension}")
        return pd.DataFrame()

    logger.info(f"Found {len(csv_files)} MachineLearningCSV files to load")

    # Load and concatenate all files
    dfs = []
    for file in csv_files:
        logger.info(f"Loading {file.name}")
        try:
            df = pd.read_csv(
                file,
                encoding="latin1",
                low_memory=False
            )
            dfs.append(df)
        except Exception as e:
            logger.error(f"Error loading {file.name}: {e}")
            # Continue with other files

    if not dfs:
        return pd.DataFrame()

    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"MachineLearningCSV dataset shape: {combined_df.shape}")

    return combined_df

def generate_synthetic_data(n_samples: int = 1000, random_state: int = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic data with identical schema for testing.

    Args:
        n_samples: Number of samples to generate
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (features_df, metadata_df)
    """
    if random_state is None:
        random_state = config.get("seed", 42)

    np.random.seed(random_state)

    logger.info(f"Generating {n_samples} synthetic samples")

    # Define feature names similar to CIC-IDS2017
    feature_names = [
        'Destination Port', 'Protocol', 'Flow Duration', 'Total Fwd Packets',
        'Total Backward Packets', 'Total Length of Fwd Packets',
        'Total Length of Bwd Packets', 'Fwd Packet Length Max',
        'Fwd Packet Length Min', 'Fwd Packet Length Mean',
        'Fwd Packet Length Std', 'Bwd Packet Length Max',
        'Bwd Packet Length Min', 'Bwd Packet Length Mean',
        'Bwd Packet Length Std', 'Flow Bytes/s', 'Flow Packets/s',
        'Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min',
        'Fwd IAT Total', 'Fwd IAT Mean', 'Fwd IAT Std', 'Fwd IAT Max',
        'Fwd IAT Min', 'Bwd IAT Total', 'Bwd IAT Mean', 'Bwd IAT Std',
        'Bwd IAT Max', 'Bwd IAT Min', 'Fwd PSH Flags', 'Bwd PSH Flags',
        'Fwd URG Flags', 'Bwd URG Flags', 'Fwd Header Length',
        'Bwd Header Length', 'Fwd Packets/s', 'Bwd Packets/s',
        'Min Packet Length', 'Max Packet Length', 'Packet Length Mean',
        'Packet Length Std', 'Packet Length Variance', 'FIN Flag Count',
        'SYN Flag Count', 'RST Flag Count', 'PSH Flag Count',
        'ACK Flag Count', 'URG Flag Count', 'CWE Flag Count',
        'ECE Flag Count', 'Down/Up Ratio', 'Average Packet Size',
        'Avg Fwd Segment Size', 'Avg Bwd Segment Size',
        'Fwd Header Length.1'  # Duplicate column to be dropped
    ]

    # Generate random feature data
    features_data = {}
    for feat in feature_names:
        if 'Length' in feat or 'Packet' in feat or 'Flow' in feat:
            # Positive values
            features_data[feat] = np.abs(np.random.normal(100, 50, n_samples))
        elif 'Count' in feat:
            # Small integer counts
            features_data[feat] = np.random.poisson(2, n_samples)
        elif 'Ratio' in feat:
            # Ratios
            features_data[feat] = np.random.uniform(0, 5, n_samples)
        elif 'IAT' in feat:
            # Inter-arrival times
            features_data[feat] = np.abs(np.random.exponential(1, n_samples))
        else:
            # Default
            features_data[feat] = np.random.normal(0, 1, n_samples)

    features_df = pd.DataFrame(features_data)

    # Generate metadata
    metadata_df = pd.DataFrame({
        'Flow ID': [f'FLOW{i:08d}' for i in range(n_samples)],
        'Source IP': [f'{np.random.randint(1, 255)}.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}'
                      for _ in range(n_samples)],
        'Source Port': np.random.randint(1024, 65535, n_samples),
        'Destination IP': [f'{np.random.randint(1, 255)}.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}'
                           for _ in range(n_samples)],
        'Timestamp': pd.date_range(start='2023-01-01', periods=n_samples, freq='1min')
    })

    # Generate labels with realistic distribution
    # Mostly benign, with various attack types
    labels = ['BENIGN'] * int(n_samples * 0.7)  # 70% benign

    attack_types = [
        'DoS Hulk', 'DoS GoldenEye', 'DoS Slowloris', 'DoS Slowhttptest',
        'DDOS attack-HOIC', 'DDOS attack-LOIC-UDP', 'DDOS attack-LOIC',
        'Bot', 'Web Attack Brute Force', 'Web Attack XSS',
        'Web Attack Sql Injection', 'Infiltration', 'PortScan',
        'FTP-Patator', 'SSH-Patator'
    ]

    # Distribute attacks among remaining 30%
    n_attacks = n_samples - len(labels)
    attacks_per_type = n_attacks // len(attack_types)
    remainder = n_attacks % len(attack_types)

    for i, attack_type in enumerate(attack_types):
        count = attacks_per_type + (1 if i < remainder else 0)
        labels.extend([attack_type] * count)

    # Trim or extend to exact n_samples
    if len(labels) > n_samples:
        labels = labels[:n_samples]
    elif len(labels) < n_samples:
        labels.extend(['BENIGN'] * (n_samples - len(labels)))

    np.random.shuffle(labels)  # Shuffle labels

    metadata_df['Label'] = labels

    # Normalize labels
    metadata_df['Label'] = metadata_df['Label'].apply(normalize_label)

    # Add flow_id
    features_df['flow_id'] = range(len(features_df))
    metadata_df['flow_id'] = range(len(metadata_df))

    logger.info(f"Generated synthetic data with label distribution:")
    logger.info(metadata_df['Label'].value_counts().head())

    return features_df, metadata_df

def load_data(synthetic: bool = False, make_synthetic: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main data loading function.

    Args:
        synthetic: If True, load synthetic data instead of real data
        make_synthetic: If True, generate and save synthetic data

    Returns:
        Tuple of (features_df, metadata_df)
    """
    if synthetic or make_synthetic:
        features_df, metadata_df = generate_synthetic_data()
        if make_synthetic:
            # Save synthetic data
            processed_dir = config.get("dataset.processed_dir")
            Path(processed_dir).mkdir(parents=True, exist_ok=True)
            features_df.to_parquet(
                Path(processed_dir) / "synthetic_features.parquet",
                compression='zstd'
            )
            metadata_df.to_parquet(
                Path(processed_dir) / "synthetic_metadata.parquet",
                compression='zstd'
            )
            logger.info("Saved synthetic data to processed directory")
        return features_df, metadata_df
    else:
        return load_traffic_labelling_data()

if __name__ == "__main__":
    # Test the data loader
    logger.info("Testing data loader...")

    # Test synthetic data generation
    logger.info("Generating synthetic data...")
    features, metadata = load_data(synthetic=True)
    logger.info(f"Synthetic features shape: {features.shape}")
    logger.info(f"Synthetic metadata shape: {metadata.shape}")
    logger.info(f"Synthetic label distribution:\n{metadata['Label'].value_counts()}")

    # Test real data loading (if available)
    try:
        logger.info("Attempting to load real data...")
        features_real, metadata_real = load_traffic_labelling_data()
        logger.info(f"Real features shape: {features_real.shape}")
        logger.info(f"Real metadata shape: {metadata_real.shape}")
        if 'Label' in metadata_real.columns:
            logger.info(f"Real label distribution:\n{metadata_real['Label'].value_counts()}")
    except FileNotFoundError as e:
        logger.warning(f"Could not load real data: {e}")
        logger.info("This is expected if raw data is not placed in data/raw/")

    logger.info("Data loader test complete!")