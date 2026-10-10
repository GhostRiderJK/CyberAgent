"""
Preprocessing module for CyberAgent.

Loading, cleaning, label grouping, splitting and leakage-safe preprocessing.

Key rules:
  * Everything that learns from data (imputer, scaler, feature selector) is fit
    on the TRAINING split only.
  * Features and metadata are always linked by ``flow_id``, never by row order.
  * ``X_*`` / ``y_*`` returned by ``split_data`` are indexed by ``flow_id``.
"""
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from cyberagent.config import config
from cyberagent.feature_selection import FeatureSelector
from cyberagent.logging_setup import logger

MIN_CLASS_ROWS = 50            # warn when a class has fewer rows than this in a split
CROSS_LABEL_LIMIT_PCT = 0.5    # above this, cross-label duplicates need a manual decision

# Features that cannot be negative (a negative value is a CICFlowMeter artefact).
IMPOSSIBLE_NEGATIVE_FEATURES = [
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
    'Avg Fwd Segment Size', 'Avg Bwd Segment Size',
]

# Dash look-alikes seen in CIC-IDS2017 labels: the cp1252 dash (\x96/\x97 when read
# as latin-1), the Unicode replacement character, and the Unicode dash block.
_DASH_RE = re.compile("[\u2010-\u2015\u2212\ufe58\ufe63\uff0d\ufffd\x96\x97]")
_CONTROL_RE = re.compile("[\x00-\x1f\x7f-\x9f]")


def normalize_label(value: Any) -> str:
    """Return a clean label: odd dashes -> '-', control chars removed, spaces collapsed.

    Idempotent: normalize_label(normalize_label(x)) == normalize_label(x).
    """
    text = _DASH_RE.sub("-", str(value))
    text = _CONTROL_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


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

    if 'flow_id' not in features_df.columns:
        raise ValueError("flow_id column missing in features_df")
    if 'flow_id' not in metadata_df.columns:
        raise ValueError("flow_id column missing in metadata_df")

    return features_df, metadata_df


def _count_groups(frame: pd.DataFrame, cols: list) -> int:
    """Number of distinct feature-value groups in ``frame`` (NaN counts as a value)."""
    if frame.empty:
        return 0
    return int(frame.groupby(cols, dropna=False, sort=False).ngroups)


def _remove_duplicates(df: pd.DataFrame, cols: list, st: Dict[str, Any]) -> pd.DataFrame:
    """Remove duplicate feature rows. NaN-safe: NaN is treated as an ordinary value.

    Rule: rows whose features are identical but whose labels differ (the true label is
    unknowable) are ALL dropped when they are < CROSS_LABEL_LIMIT_PCT of the data.
    For identical rows with the same label, exactly one is kept.
    """
    st.update(
        duplicate_rows=0, cross_label_groups=0, cross_label_rows=0, cross_label_pct=0.0,
        same_label_groups=0, same_label_rows=0, dropped_cross_label=0, dropped_same_label=0,
    )
    if not cols:
        logger.warning("No feature columns available for duplicate checking.")
        return df

    dup_all = df.duplicated(subset=cols, keep=False).to_numpy()
    n_dup = int(dup_all.sum())
    st["duplicate_rows"] = n_dup
    if n_dup == 0:
        logger.info("No duplicate feature rows found.")
        return df
    logger.warning(f"Found {n_dup} duplicate feature rows.")

    if 'Label' not in df.columns:
        logger.warning("Label column not found, using standard duplicate removal.")
        drop = df.duplicated(subset=cols, keep='first').to_numpy()
        st["dropped_same_label"] = int(drop.sum())
        return df[~drop].reset_index(drop=True)

    dup_pos = np.flatnonzero(dup_all)
    dups = df.iloc[dup_pos]
    n_labels = (
        dups.groupby(cols, dropna=False, sort=False)['Label'].transform('nunique').to_numpy()
    )
    is_cross = n_labels > 1
    cross_pos, same_pos = dup_pos[is_cross], dup_pos[~is_cross]

    pct = 100.0 * len(cross_pos) / len(df)
    st.update(
        cross_label_rows=int(len(cross_pos)), same_label_rows=int(len(same_pos)),
        cross_label_groups=_count_groups(dups[is_cross], cols),
        same_label_groups=_count_groups(dups[~is_cross], cols),
        cross_label_pct=pct,
    )
    logger.info(
        f"Duplicate analysis: {st['cross_label_groups']} cross-label groups "
        f"({st['cross_label_rows']} rows, {pct:.4f}%), "
        f"{st['same_label_groups']} same-label groups ({st['same_label_rows']} rows)"
    )

    if pct >= CROSS_LABEL_LIMIT_PCT:
        logger.warning(
            f"Cross-label duplicate rows ({pct:.4f}%) >= {CROSS_LABEL_LIMIT_PCT}%. "
            "No changes made to duplicate handling. Manual review required."
        )
        return df

    same = df.iloc[same_pos]
    drop_same_pos = same_pos[same.duplicated(subset=cols, keep='first').to_numpy()]

    keep = np.ones(len(df), dtype=bool)
    keep[cross_pos] = False
    keep[drop_same_pos] = False
    st["dropped_cross_label"] = int(len(cross_pos))
    st["dropped_same_label"] = int(len(drop_same_pos))
    logger.info(
        f"Dropped {st['dropped_cross_label']} cross-label duplicate rows and "
        f"{st['dropped_same_label']} same-label duplicate rows."
    )
    return df[keep].reset_index(drop=True)


def clean_data(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    handle_impossible_negatives: bool = True,
    drop_constant_columns: bool = True,
    stats: Optional[Dict[str, Any]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Clean the dataset by:
    - Setting impossible negative values to NaN (they are imputed later, on train only)
    - Removing duplicate feature rows (flow_id and Label are not part of the key)
    - Dropping constant columns
    - Filtering metadata to the flow_ids that survive in features

    Rows are only ever removed by the duplicate step, never because of NaN.

    Args:
        stats: optional dict that is filled with the computed counts for each stage
               (rows_in, duplicate counts, rows_removed_total, rows_out, ...).

    Returns:
        Tuple of (cleaned_features_df, cleaned_metadata_df)
    """
    logger.info("Starting data cleaning...")

    features_clean = features_df.copy()
    metadata_clean = metadata_df.copy()
    st: Dict[str, Any] = {"rows_in": len(features_clean)}

    neg_counts: Dict[str, int] = {}
    if handle_impossible_negatives:
        for feat in [f for f in IMPOSSIBLE_NEGATIVE_FEATURES if f in features_clean.columns]:
            neg_mask = features_clean[feat] < 0
            neg_count = int(neg_mask.sum())
            if neg_count > 0:
                logger.warning(f"Feature {feat} has {neg_count} negative values. Setting to NaN.")
                features_clean.loc[neg_mask, feat] = np.nan
                neg_counts[feat] = neg_count
    st["negative_values_set_to_nan"] = neg_counts

    check_cols = [c for c in features_clean.columns if c not in ('flow_id', 'Label')]
    st["rows_with_nan_after_negative_handling"] = (
        int(features_clean[check_cols].isna().any(axis=1).sum()) if check_cols else 0
    )

    features_clean = _remove_duplicates(features_clean, check_cols, st)
    st["rows_after_dedupe"] = len(features_clean)

    constant_cols = []
    if drop_constant_columns:
        for col in features_clean.columns:
            if col in ('flow_id', 'Label'):
                continue
            if features_clean[col].nunique(dropna=False) == 1:
                constant_cols.append(col)
        if constant_cols:
            logger.warning(f"Dropping constant columns: {constant_cols}")
            features_clean = features_clean.drop(columns=constant_cols)
    st["constant_columns"] = constant_cols
    st["rows_after_constant_drop"] = len(features_clean)

    if 'flow_id' in features_clean.columns and 'flow_id' in metadata_clean.columns:
        keep_ids = set(features_clean['flow_id'])
        metadata_clean = metadata_clean[metadata_clean['flow_id'].isin(keep_ids)].reset_index(drop=True)
        logger.info(f"After syncing metadata to feature flow_ids: metadata shape {metadata_clean.shape}")

    st["rows_removed_total"] = st["dropped_cross_label"] + st["dropped_same_label"]
    st["rows_out"] = len(features_clean)
    if st["rows_in"] - st["rows_removed_total"] != st["rows_out"]:
        raise RuntimeError(f"Row accounting mismatch in clean_data: {st}")

    logger.info(
        f"Data cleaning complete. rows {st['rows_in']} -> {st['rows_out']} "
        f"(removed {st['rows_removed_total']}). Features shape: {features_clean.shape}"
    )
    if stats is not None:
        stats.update(st)
    return features_clean, metadata_clean


def apply_label_grouping(
    features_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    label_mapping_config: Optional[Dict[str, str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """
    Normalise labels and apply label grouping.

    Args:
        label_mapping_config: None -> use config ``preprocessing.label_groups``;
                              {} -> identity mapping over the labels present;
                              dict -> use that mapping.

    Returns:
        Tuple of (features_df_with_label, metadata_df, label_mapping_used)
    """
    logger.info("Applying label grouping...")
    features_df = features_df.copy()

    if 'Label' not in features_df.columns:
        features_df = features_df.merge(metadata_df[['flow_id', 'Label']], on='flow_id', how='left')

    if label_mapping_config is None:
        label_mapping_config = config.get("preprocessing.label_groups", {})

    features_df['Label'] = features_df['Label'].map(normalize_label)

    if not label_mapping_config:
        label_mapping_config = {label: label for label in features_df['Label'].unique()}
        logger.info("No label grouping configured. Using identity mapping.")
    else:
        logger.info(f"Applying label grouping: {label_mapping_config}")

    features_df['Label'] = features_df['Label'].map(label_mapping_config).fillna(features_df['Label'])

    # Safety net: any other "Web Attack ..." variant is grouped too.
    web_attack_mask = features_df['Label'].str.startswith('Web Attack')
    features_df.loc[web_attack_mask, 'Label'] = 'Web Attack'

    return features_df, metadata_df, label_mapping_config


def _warn_small_classes(y_train: pd.Series, y_val: pd.Series, y_test: pd.Series) -> None:
    """Log loudly when a class is missing or has too few rows in a split."""
    all_classes = sorted(set(y_train) | set(y_val) | set(y_test))
    for name, y in (("train", y_train), ("val", y_val), ("test", y_test)):
        counts = y.value_counts()
        for cls in all_classes:
            n = int(counts.get(cls, 0))
            if n == 0:
                logger.error(f"Class '{cls}' is MISSING from the {name} split.")
            elif n < MIN_CLASS_ROWS:
                logger.warning(f"Class '{cls}' has only {n} rows in the {name} split (< {MIN_CLASS_ROWS}).")


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
    Split into train / validation / test. Zero-day holdout labels are removed first.

    Features and metadata are linked by ``flow_id``. The returned X and y are indexed by
    ``flow_id``; each meta frame keeps a ``flow_id`` column and is row-aligned with X.

    split_mode:
      "stratified" - random split stratified by Label (default).
      "time_aware" - chronological split on metadata ``Timestamp`` (earliest -> train).
                     Attacks happen on different days, so classes may be missing from
                     later splits; this is reported loudly.

    Returns:
        (X_train, X_val, X_test, y_train, y_val, y_test, train_meta, val_meta, test_meta)
    """
    if not np.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError("Split ratios must sum to 1.0")
    if split_mode not in ("stratified", "time_aware"):
        raise ValueError(f"Unknown split_mode: {split_mode}")

    has_label = 'Label' in features_df.columns
    holdout_labels = config.get("preprocessing.zero_day_holdout_labels", [])
    if holdout_labels and has_label:
        holdout_mask = features_df['Label'].isin(holdout_labels)
        if holdout_mask.any():
            features_df = features_df[~holdout_mask]

    features_df = features_df.reset_index(drop=True)
    flow_ids = features_df['flow_id'].to_numpy()

    if not metadata_df['flow_id'].is_unique:
        raise ValueError("metadata_df has duplicate flow_id values")
    meta_by_id = metadata_df.set_index('flow_id')
    missing = np.setdiff1d(flow_ids, meta_by_id.index.to_numpy())
    if len(missing) > 0:
        raise ValueError(f"{len(missing)} flow_ids in features are missing from metadata (e.g. {missing[:5]})")

    n = len(features_df)
    indices = np.arange(n)

    if split_mode == "stratified":
        labels = features_df['Label'].to_numpy() if has_label else None
        train_idx, temp_idx = train_test_split(
            indices, train_size=train_ratio, random_state=seed, stratify=labels
        )
        val_share = val_ratio / (val_ratio + test_ratio)
        temp_labels = labels[temp_idx] if labels is not None else None
        val_idx, test_idx = train_test_split(
            temp_idx, train_size=val_share, random_state=seed, stratify=temp_labels
        )
    else:
        if 'Timestamp' not in meta_by_id.columns:
            raise ValueError("time_aware split needs a 'Timestamp' column in the metadata")
        ts = pd.to_datetime(meta_by_id.loc[flow_ids, 'Timestamp'], errors='coerce').to_numpy()
        if pd.isna(ts).any():
            logger.warning(f"{int(pd.isna(ts).sum())} rows have an unparseable Timestamp; placed last.")
        order = np.argsort(ts, kind="stable")
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        train_idx = order[:n_train]
        val_idx = order[n_train:n_train + n_val]
        test_idx = order[n_train + n_val:]

    def _take(idx):
        sub = features_df.iloc[idx]
        ids = sub['flow_id'].to_numpy()
        drop_cols = ['flow_id', 'Label'] if has_label else ['flow_id']
        X = sub.drop(columns=drop_cols)
        X.index = pd.Index(ids, name='flow_id')
        if has_label:
            y = pd.Series(sub['Label'].to_numpy(), index=X.index, name='Label')
        else:
            y = pd.Series(dtype=object)
        meta = meta_by_id.loc[ids].reset_index()      # flow_id column + aligned rows
        meta.index = pd.Index(ids)
        return X, y, meta

    X_train, y_train, train_meta = _take(train_idx)
    X_val, y_val, val_meta = _take(val_idx)
    X_test, y_test, test_meta = _take(test_idx)

    if has_label:
        _warn_small_classes(y_train, y_val, y_test)

    return X_train, X_val, X_test, y_train, y_val, y_test, train_meta, val_meta, test_meta


def preprocess_train_fit(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    correlation_threshold: float = 0.95,
    feature_selection_method: str = "mutual_info",
    top_k_features: int = 40,
    seed: int = 42,
    return_selector: bool = False,
):
    """
    Fit imputer, scaler and feature selector on TRAINING data only.

    Feature selection = constant-column removal, correlation pruning
    (``correlation_threshold`` >= 1.0 disables it) and mutual-information top-K using
    ``y_train`` (see ``FeatureSelector``).

    feature_selection_method:
      "mutual_info" - correlation pruning, then top ``top_k_features`` by mutual information.
      "none"        - correlation pruning only (no top-K ranking).
      "variance"    - deprecated alias of "mutual_info".

    Returns:
        (imputer, scaler, feature_mask), or (imputer, scaler, feature_mask, selector) when
        ``return_selector`` is True. feature_mask is a boolean array over X_train.columns.
    """
    if len(X_train) != len(y_train):
        raise ValueError("X_train and y_train must have the same length")

    method = feature_selection_method
    if method == "variance":
        logger.warning("feature_selection_method 'variance' is deprecated; using 'mutual_info'.")
        method = "mutual_info"
    if method not in ("mutual_info", "none"):
        raise ValueError(f"Unknown feature selection method: {feature_selection_method}")

    X_replaced = X_train.replace([np.inf, -np.inf], np.nan)

    imputer = SimpleImputer(strategy='median', keep_empty_features=True)
    imputer.fit(X_replaced)
    scaler = StandardScaler()
    scaler.fit(imputer.transform(X_replaced))

    selector = FeatureSelector(
        corr_threshold=correlation_threshold,
        top_k=top_k_features if method == "mutual_info" else None,
        seed=seed,
    )
    selector.fit(X_replaced, y_train)

    keep = set(selector.selected_)
    feature_mask = np.array([c in keep for c in X_train.columns], dtype=bool)

    if return_selector:
        return imputer, scaler, feature_mask, selector
    return imputer, scaler, feature_mask


def preprocess_transform(
    X: pd.DataFrame,
    imputer: SimpleImputer,
    scaler: StandardScaler,
    feature_mask: np.ndarray
) -> pd.DataFrame:
    """Transform data with the fitted preprocessors and keep the selected features."""
    X_replaced = X.replace([np.inf, -np.inf], np.nan)
    X_scaled = scaler.transform(imputer.transform(X_replaced))
    selected_features = X.columns[feature_mask]
    return pd.DataFrame(X_scaled[:, feature_mask], columns=selected_features, index=X.index)


def handle_imbalance(
    y_train: pd.Series,
    method: str = "class_weight"
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Handle class imbalance.

    Args:
        method: "class_weight" (balanced weights returned in info) or "smote" (not implemented)
    """
    if method == "class_weight":
        from sklearn.utils.class_weight import compute_class_weight
        classes = np.unique(y_train)
        weights = compute_class_weight('balanced', classes=classes, y=y_train)
        return y_train, {'class_weight': dict(zip(classes, weights))}
    elif method == "smote":
        raise NotImplementedError("SMOTE not implemented yet")
    raise ValueError(f"Unknown imbalance handling method: {method}")


EXPECTED_SUPERVISED_LABELS = {
    "BENIGN", "Bot", "DDoS", "DoS GoldenEye", "DoS Hulk",
    "DoS Slowhttptest", "DoS slowloris", "FTP-Patator",
    "PortScan", "SSH-Patator", "Web Attack",
}


def example_preprocessing_pipeline(save_outputs: bool = True) -> Dict[str, Any]:
    """
    Load -> label grouping -> clean -> holdout -> split -> fit/transform preprocessing.

    Args:
        save_outputs: when True (default) writes the zero-day holdout parquet files to
                      ``dataset.processed_dir`` and ``selected_features.csv`` to
                      ``results/tables``. Tests should pass False.

    Returns:
        dict with X_train/X_val/X_test (preprocessed, indexed by flow_id), y_train/y_val/y_test,
        imbalance_info, plus selector, clean_stats and the holdout frames.
    """
    features_df, metadata_df = load_reduced_data()
    features_with_label, metadata_with_label, _ = apply_label_grouping(features_df, metadata_df)

    clean_stats: Dict[str, Any] = {}
    features_clean, metadata_clean = clean_data(
        features_with_label, metadata_with_label,
        handle_impossible_negatives=config.get("preprocessing.handle_impossible_negatives", True),
        drop_constant_columns=config.get("preprocessing.drop_constant_columns", True),
        stats=clean_stats,
    )

    holdout_labels = config.get("preprocessing.zero_day_holdout_labels", [])
    holdout_mask = features_clean['Label'].isin(holdout_labels)
    supervised_features = features_clean[~holdout_mask].reset_index(drop=True)
    holdout_features = features_clean[holdout_mask].reset_index(drop=True)
    supervised_metadata = metadata_clean[metadata_clean['flow_id'].isin(set(supervised_features['flow_id']))]
    holdout_metadata = metadata_clean[metadata_clean['flow_id'].isin(set(holdout_features['flow_id']))]

    if len(holdout_features) > 0:
        logger.info(f"Holdout label distribution:\n{holdout_features['Label'].value_counts()}")
        if set(holdout_features['Label'].unique()) != set(holdout_labels):
            raise AssertionError(
                f"Holdout set mismatch. Expected: {set(holdout_labels)}, "
                f"Got: {set(holdout_features['Label'].unique())}"
            )
    else:
        logger.info("No holdout samples found.")

    if save_outputs:
        processed_dir = Path(config.get("dataset.processed_dir"))
        processed_dir.mkdir(parents=True, exist_ok=True)
        holdout_features.to_parquet(processed_dir / "holdout_zero_day.parquet", compression='zstd')
        holdout_metadata.reset_index(drop=True).to_parquet(
            processed_dir / "holdout_zero_day_meta.parquet", compression='zstd'
        )

    (X_train, X_val, X_test,
     y_train, y_val, y_test,
     train_meta, val_meta, test_meta) = split_data(
        supervised_features, supervised_metadata,
        split_mode=config.get("split.mode", "stratified"),
        train_ratio=config.get("split.train_ratio", 0.7),
        val_ratio=config.get("split.val_ratio", 0.15),
        test_ratio=config.get("split.test_ratio", 0.15),
        seed=config.get("split.seed", 42),
    )

    for df, name in [(X_train, "X_train"), (X_val, "X_val"), (X_test, "X_test")]:
        for forbidden in ('flow_id', 'Label'):
            if forbidden in df.columns:
                raise AssertionError(f"{forbidden} found in {name}")

    logger.info(f"y_train distribution:\n{y_train.value_counts()}")
    logger.info(f"y_val distribution:\n{y_val.value_counts()}")
    logger.info(f"y_test distribution:\n{y_test.value_counts()}")

    actual_labels = set(pd.concat([y_train, y_val, y_test]).unique())
    if actual_labels != EXPECTED_SUPERVISED_LABELS:
        raise AssertionError(
            f"Supervised label set mismatch. Expected: {EXPECTED_SUPERVISED_LABELS}, Got: {actual_labels}"
        )

    imputer, scaler, feature_mask, selector = preprocess_train_fit(
        X_train, y_train,
        correlation_threshold=config.get("preprocessing.correlation_threshold", 0.95),
        feature_selection_method=config.get("preprocessing.feature_selection_method", "mutual_info"),
        top_k_features=config.get("preprocessing.top_k_features", 40),
        seed=config.get("split.seed", 42),
        return_selector=True,
    )

    X_train_p = preprocess_transform(X_train, imputer, scaler, feature_mask)
    X_val_p = preprocess_transform(X_val, imputer, scaler, feature_mask)
    X_test_p = preprocess_transform(X_test, imputer, scaler, feature_mask)

    logger.info(
        f"Feature selection: {X_train.shape[1]} in -> {X_train_p.shape[1]} out "
        f"({len(selector.dropped_constant_)} constant, {len(selector.dropped_corr_)} correlated, "
        f"{len(selector.dropped_selection_)} low mutual information)"
    )
    logger.info(f"Feature names: {list(X_train_p.columns)}")
    if save_outputs:
        selector.save_report(Path("results/tables") / "selected_features.csv")

    y_train_p, imbalance_info = handle_imbalance(y_train, method=config.get("imbalance.method", "class_weight"))

    return {
        'X_train': X_train_p, 'X_val': X_val_p, 'X_test': X_test_p,
        'y_train': y_train_p, 'y_val': y_val, 'y_test': y_test,
        'imbalance_info': imbalance_info,
        'selector': selector, 'clean_stats': clean_stats,
        'holdout_features': holdout_features, 'holdout_metadata': holdout_metadata,
    }
