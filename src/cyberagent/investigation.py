"""
Investigation tools for CyberAgent.
Implements deterministic tools for the investigation agent.
"""
import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import json
from cyberagent.config import config
from cyberagent.data_loader import load_data
from cyberagent.preprocess import example_preprocessing_pipeline
from cyberagent.train import train_lightgbm
from cyberagent.explain import explain_instance_top_features, explain_model
import joblib
from cyberagent.logging_setup import logger

# Global variables to cache loaded data and models
_features_df_full: Optional[pd.DataFrame] = None   # with flow_id column, all original features
_features_df_model: Optional[pd.DataFrame] = None  # without flow_id, only selected features for model
_metadata_df: Optional[pd.DataFrame] = None        # with flow_id column
_model: Any = None
_explainer: Any = None
_preprocess_artifacts: Optional[Dict[str, Any]] = None  # imputer/scaler fitted during preprocessing

def _initialize_data_and_model():
    """Initialize data and model if not already loaded."""
    global _features_df_full, _features_df_model, _metadata_df, _model, _explainer, _preprocess_artifacts

    if _features_df_full is not None and _features_df_model is not None and _metadata_df is not None and _model is not None:
        return

    logger.info("Initializing data and model for investigation tools...")

    # Load preprocessed data (assuming it exists from training)
    processed_dir = Path(config.get("dataset.processed_dir"))
    features_path = processed_dir / "flows_features.parquet"
    metadata_path = processed_dir / "flows_meta.parquet"
    selected_features_path = Path("results/tables/selected_features.csv")

    if not (features_path.exists() and metadata_path.exists() and selected_features_path.exists()):
        logger.error("Preprocessed data (features, metadata, selected features) not found. Please run the reduction and preprocessing steps.")
        return

    # Load features and metadata, keep flow_id as column for lookup
    _features_df_full = pd.read_parquet(features_path)   # flow_id is a column
    _metadata_df = pd.read_parquet(metadata_path)        # flow_id is a column

    # Load selected features
    selected_features_df = pd.read_csv(selected_features_path)
    kept_features = selected_features_df[selected_features_df['status'] == 'kept']['feature'].tolist()
    # Ensure the kept features are present in the features (excluding flow_id)
    feature_cols = [c for c in _features_df_full.columns if c != 'flow_id']
    kept_features = [f for f in kept_features if f in feature_cols]

    if not kept_features:
        logger.error("No matching selected features found in the features data.")
        return

    # Features for the model (without the flow_id column)
    _features_df_model = _features_df_full[kept_features]
    logger.info(f"Loaded preprocessed data: {_features_df_full.shape}")
    logger.info(f"Filtered to {len(kept_features)} selected features for model: {_features_df_model.shape}")

    # Ensure the indices are aligned (they should be, as both come from the same parquet files)
    # We'll reset index to be safe, but we rely on flow_id for lookup.
    # For simplicity, we keep the default index (0..n-1) and assume the rows are in the same order.
    # To be safe, we can set index to flow_id for both dataframes, but we'll keep as is and use flow_id to locate the row.

    # Load fitted preprocessing artifacts (imputer/scaler) if available so
    # serving applies the same transformations as training did.
    artifacts_path = processed_dir / "preprocess_artifacts.joblib"
    if artifacts_path.exists():
        _preprocess_artifacts = joblib.load(artifacts_path)
        logger.info("Loaded preprocessing artifacts (imputer/scaler) for serving")
    else:
        _preprocess_artifacts = None
        logger.warning("preprocess_artifacts.joblib not found; serving uses raw features "
                       "(run `make preprocess` to align with the training pipeline)")

    # Load or train model
    model_path = Path("models/lightgbm.joblib")
    if model_path.exists():
        _model = joblib.load(model_path)
        logger.info("Loaded existing LightGBM model")
    else:
        logger.info("Training LightGBM model...")
        data_dict = example_preprocessing_pipeline(save_outputs=False)
        X_train = data_dict['X_train']
        y_train = data_dict['y_train']
        X_val = data_dict['X_val']
        y_val = data_dict['y_val']
        _model = train_lightgbm(X_train, y_train, X_val, y_val)
        # Save the model
        Path("models").mkdir(parents=True, exist_ok=True)
        joblib.dump(_model, model_path)
        logger.info("Saved LightGBM model")

    # Initialize SHAP explainer - use only feature columns (we already have _features_df_model without flow_id)
    logger.info("Initializing SHAP explainer...")
    _explainer, _ = explain_model(_model, _features_df_model, _features_df_model.head(100))  # Use subset for background
    logger.info("SHAP explainer initialized")

def _get_model_features_for_flow_id(flow_id: Union[int, str]) -> pd.DataFrame:
    """
    Get the model features (selected features only) for a given flow_id.
    Returns a single-row DataFrame with columns matching the model's expected features.
    """
    _initialize_data_and_model()
    if _features_df_full is None or _features_df_model is None:
        raise RuntimeError("Data not initialized")

    # Convert flow_id to appropriate type for comparison
    try:
        flow_id_numeric = int(flow_id)
    except ValueError:
        flow_id_numeric = flow_id

    # Find the row with matching flow_id in the full features dataframe
    mask = _features_df_full['flow_id'] == flow_id_numeric
    if not mask.any():
        # Try in metadata if not found in features
        mask = _metadata_df['flow_id'] == flow_id_numeric
        if not mask.any():
            raise ValueError(f"Flow ID {flow_id} not found in dataset")
        # Get the index from metadata to locate the corresponding features row
        idx = _metadata_df.index[mask][0]
    else:
        idx = _features_df_full.index[mask][0]

    # Get the model features for that row
    features_row = _features_df_model.iloc[idx:idx+1]  # single row DataFrame
    return _transform_for_model(features_row)

def _transform_for_model(features_row: pd.DataFrame) -> pd.DataFrame:
    """Apply the fitted imputer/scaler so serving matches the training pipeline.

    The imputer/scaler were fitted on ALL pre-selection feature columns, so the
    row is padded to that column set, transformed, then reduced to the kept
    features the model was trained on.
    """
    if _preprocess_artifacts is None:
        return features_row
    imputer = _preprocess_artifacts.get('imputer')
    scaler = _preprocess_artifacts.get('scaler')
    full_names = _preprocess_artifacts.get('feature_names')       # columns imputer/scaler were fitted on
    model_names = _preprocess_artifacts.get('selected_feature_names')  # columns the model was trained on
    if imputer is None or scaler is None or not full_names or not model_names:
        return features_row
    X = features_row.reindex(columns=full_names)
    X = X.replace([np.inf, -np.inf], np.nan)
    X = pd.DataFrame(scaler.transform(imputer.transform(X)), columns=full_names, index=features_row.index)
    return X[model_names]

def get_flow_record(flow_id: Union[int, str]) -> Dict[str, Any]:
    """Connection-level fields of a flow, read from the stored record.

    These are the only IPs and ports the product can state as fact: they come from
    flows_meta.parquet, not from a narrative. Fields the reduced dataset does not keep
    are returned as null and listed in `missing_fields`, so a caller can say "not in the
    record" instead of showing a plausible 0.
    """
    record: Dict[str, Any] = {
        'flow_id': None,
        'source_ip': None,
        'source_port': None,
        'destination_ip': None,
        'destination_port': None,
        'protocol': None,
        'timestamp': None,
        'missing_fields': [],
        'available': False,
    }
    try:
        _initialize_data_and_model()
    except Exception as e:  # data not prepared yet / model missing
        logger.warning(f"Flow record unavailable for {flow_id}: {e}")
        record['reason'] = f'Flow metadata could not be loaded: {e}'
        return record

    if _metadata_df is None:
        record['reason'] = 'Flow metadata is not loaded.'
        return record

    try:
        flow_id_numeric = int(flow_id)
    except (TypeError, ValueError):
        flow_id_numeric = flow_id
    matches = _metadata_df.index[_metadata_df['flow_id'] == flow_id_numeric]
    if len(matches) == 0:
        record['reason'] = f'flow_id {flow_id} is not in the stored flow metadata.'
        return record

    row = _metadata_df.loc[matches[0]]
    # flows_meta.parquet only keeps the source side of the conversation; the feature
    # frame carries the destination port and protocol for the same row, so those
    # identifiers are read from there instead of being reported as unknown.
    pos = int(_metadata_df.index.get_loc(matches[0]))
    feat_row = _features_df_full.iloc[pos] if (
        _features_df_full is not None and pos < len(_features_df_full)) else None

    for out_key, column in (('source_ip', 'Source IP'), ('source_port', 'Source Port'),
                            ('destination_ip', 'Destination IP'), ('destination_port', 'Destination Port'),
                            ('protocol', 'Protocol')):
        value = row[column] if column in _metadata_df.columns else None
        if (value is None or pd.isna(value)) and feat_row is not None and column in feat_row.index:
            value = feat_row[column]
        if value is None or pd.isna(value):
            record['missing_fields'].append(out_key)
            continue
        if out_key.endswith('port'):
            record[out_key] = int(value)
        elif out_key == 'protocol':
            # Stored as float64 in the feature frame; IANA protocol 6 must not be
            # reported as "6.0".
            record[out_key] = str(int(value))
        else:
            record[out_key] = str(value)

    ts = row['Timestamp'] if 'Timestamp' in _metadata_df.columns else None
    if ts is not None and pd.notna(ts):
        record['timestamp'] = str(ts)
    else:
        record['missing_fields'].append('timestamp')

    record['flow_id'] = int(row['flow_id'])
    record['available'] = True
    return record


def predict_proba(flow_id: Union[int, str]) -> Dict[str, Any]:
    """
    Get prediction probabilities for a specific flow.

    Args:
        flow_id: The flow ID to predict for

    Returns:
        Dictionary with prediction results including probabilities per class
    """
    logger.info(f"Getting prediction probabilities for flow_id: {flow_id}")

    # Get the model features for this flow
    features_row = _get_model_features_for_flow_id(flow_id)

    # Get prediction probabilities
    if hasattr(_model, 'label_encoder_'):
        # For models with label encoding (XGBoost, LightGBM with our modifications)
        proba = _model.predict_proba(features_row)
        classes = _model.label_encoder_.classes_
    else:
        # For models without label encoding
        proba = _model.predict_proba(features_row)
        classes = _model.classes_

    # Format results
    result = {
        'flow_id': flow_id,
        'predicted_class': None,
        'probabilities': {},
        'confidence': 0.0
    }

    # Get predicted class (highest probability)
    max_idx = np.argmax(proba[0])
    result['predicted_class'] = str(classes[max_idx])
    result['confidence'] = float(proba[0][max_idx])

    # Format probabilities for each class
    for idx, cls in enumerate(classes):
        result['probabilities'][str(cls)] = float(proba[0][idx])

    logger.info(f"Prediction for flow {flow_id}: {result['predicted_class']} (confidence: {result['confidence']:.4f})")
    return result

def explain_flow(flow_id: Union[int, str]) -> Dict[str, Any]:
    """
    Get SHAP explanation for a specific flow.

    Args:
        flow_id: The flow ID to explain

    Returns:
        Dictionary with SHAP explanation including top features
    """
    logger.info(f"Getting SHAP explanation for flow_id: {flow_id}")

    # Get the model features for this flow
    features_row = _get_model_features_for_flow_id(flow_id)

    # Get SHAP explanation
    try:
        top_features = explain_instance_top_features(_model, _features_df_model, features_row, top_k=10)
        explanation_error = None
    except Exception as e:
        logger.error(f"Error generating SHAP explanation: {e}")
        # Fallback to basic explanation
        top_features = []
        explanation_error = str(e)

    # Get the prediction for this flow
    pred_result = predict_proba(flow_id)

    result = {
        'flow_id': flow_id,
        'predicted_class': pred_result['predicted_class'],
        'confidence': pred_result['confidence'],
        'shap_values': [float(shap['shap_value']) for shap in top_features],
        'feature_names': [shap['feature'] for shap in top_features],
        'feature_values': [float(shap['value']) for shap in top_features],
        # The served row is post-scaler, so these are z-scores, not raw packet counts.
        'value_scale': 'standardized',
        'top_features': top_features,
        'explanation_error': explanation_error,
    }

    logger.info(f"SHAP explanation generated for flow {flow_id} with {len(top_features)} top features")
    return result

def find_related_flows(flow_id: Union[int, str],
                      time_window_minutes: int = 30,
                      same_source_dest: bool = True,
                      same_protocol: bool = True,
                      limit: int = 100) -> List[Dict[str, Any]]:
    """
    Find flows related to a given flow based on various criteria.
    Optimized version using vectorized operations.

    Args:
        flow_id: The flow ID to find related flows for
        time_window_minutes: Time window in minutes to consider for temporal proximity
        same_source_dest: Whether to require same source/destination IPs and ports
        same_protocol: Whether to require same protocol
        limit: Maximum number of related flows to return

    Returns:
        List of related flows with similarity scores (limited to `limit` entries)
    """
    logger.info(f"Finding related flows for flow_id: {flow_id}")

    # Get the target flow's metadata
    if 'flow_id' not in _metadata_df.columns:
        raise ValueError("flow_id column not found in metadata")

    # Convert flow_id to appropriate type for comparison
    try:
        flow_id_numeric = int(flow_id)
    except ValueError:
        flow_id_numeric = flow_id

    # Find the target flow
    mask = _metadata_df['flow_id'] == flow_id_numeric
    if not mask.any():
        raise ValueError(f"Flow ID {flow_id} not found in dataset")

    target_idx = _metadata_df.index[mask][0]
    target_metadata = _metadata_df.iloc[target_idx]

    # Extract target flow characteristics
    target_source_ip = target_metadata.get('Source IP')
    target_source_port = target_metadata.get('Source Port')
    target_dest_ip = target_metadata.get('Destination IP')
    target_dest_port = target_metadata.get('Destination Port')
    target_protocol = target_metadata.get('Protocol')
    target_timestamp = target_metadata.get('Timestamp')

    # Create a copy of metadata without the target flow
    candidates = _metadata_df[_metadata_df['flow_id'] != flow_id_numeric].copy()

    # Early exit if no candidates
    if len(candidates) == 0:
        return []

    # Vectorized similarity computation
    similarity_score = 0.0
    max_score = 0.0

    # Check source/destination IP and port (vectorized)
    if same_source_dest:
        max_score += 4.0
        if target_source_ip is not None:
            similarity_score += (candidates['Source IP'] == target_source_ip).astype(float)
        if target_source_port is not None and pd.notna(target_source_port):
            similarity_score += (candidates['Source Port'] == target_source_port).astype(float)
        if target_dest_ip is not None:
            similarity_score += (candidates['Destination IP'] == target_dest_ip).astype(float)
        if target_dest_port is not None and pd.notna(target_dest_port):
            similarity_score += (candidates['Destination Port'] == target_dest_port).astype(float)
    else:
        max_score += 0.0

    # Check protocol (vectorized)
    if same_protocol:
        max_score += 1.0
        if target_protocol is not None:
            similarity_score += (candidates['Protocol'] == target_protocol).astype(float)
    else:
        max_score += 0.0

    # Check temporal proximity (vectorized)
    if pd.notna(target_timestamp) and 'Timestamp' in candidates.columns:
        max_score += 1.0
        time_diff = abs((candidates['Timestamp'] - target_timestamp).dt.total_seconds()) / 60.0
        temporal_score = (1.0 - (time_diff / time_window_minutes)).clip(lower=0)
        # Only apply temporal score where time_diff <= time_window_minutes
        temporal_score = temporal_score.where(time_diff <= time_window_minutes, 0)
        similarity_score += temporal_score
    else:
        max_score += 0.0

    # Calculate similarity ratio
    if max_score > 0:
        similarity_ratio = similarity_score / max_score
    else:
        similarity_ratio = pd.Series(0.0, index=candidates.index)

    # Filter candidates with similarity >= 0.5
    related_mask = similarity_ratio >= 0.5
    related_candidates = candidates[related_mask].copy()
    related_similarities = similarity_ratio[related_mask]

    # Sort by similarity score (descending) and limit
    if len(related_candidates) > 0:
        sorted_indices = related_similarities.sort_values(ascending=False).index
        related_candidates = related_candidates.loc[sorted_indices]
        related_similarities = related_similarities.loc[sorted_indices]

        # Apply limit
        if len(related_candidates) > limit:
            related_candidates = related_candidates.head(limit)
            related_similarities = related_similarities.head(limit)

        # Build result list
        related_flows = []
        for idx, (row_idx, row) in enumerate(related_candidates.iterrows()):
            similarity = related_similarities.iloc[idx]
            # Get the features for this flow
            flow_features_full = _features_df_full.loc[_features_df_full['flow_id'] == row['flow_id']]
            if not flow_features_full.empty:
                flow_features = flow_features_full.iloc[0]
                related_flows.append({
                    'flow_id': int(row['flow_id']),
                    'similarity_score': float(similarity),
                    'source_ip': str(row.get('Source IP', '')),
                    'source_port': int(row.get('Source Port', 0)) if pd.notna(row.get('Source Port')) else None,
                    'dest_ip': str(row.get('Destination IP', '')),
                    'dest_port': int(row.get('Destination Port', 0)) if pd.notna(row.get('Destination Port')) else None,
                    'protocol': str(row.get('Protocol', '')),
                    'timestamp': str(row.get('Timestamp', '')) if pd.notna(row.get('Timestamp')) else None,
                    'features': flow_features.to_dict() if hasattr(flow_features, 'to_dict') else {}
                })

        logger.info(f"Found {len(related_flows)} related flows for flow {flow_id} (limited to {limit})")
        return related_flows

    logger.info(f"Found 0 related flows for flow {flow_id}")
    return []

def similar_known_attacks(flow_id: Union[int, str], k: int = 5) -> List[Dict[str, Any]]:
    """
    Find k similar known attacks from the dataset.

    Args:
        flow_id: The flow ID to find similar attacks for
        k: Number of similar attacks to return

    Returns:
        List of k similar known attacks
    """
    logger.info(f"Finding {k} similar known attacks for flow_id: {flow_id}")

    # Get the target flow's metadata and prediction
    if 'flow_id' not in _metadata_df.columns:
        raise ValueError("flow_id column not found in metadata")

    # Convert flow_id to appropriate type for comparison
    try:
        flow_id_numeric = int(flow_id)
    except ValueError:
        flow_id_numeric = flow_id

    # Find the target flow
    mask = _metadata_df['flow_id'] == flow_id_numeric
    if not mask.any():
        raise ValueError(f"Flow ID {flow_id} not found in dataset")

    target_idx = _metadata_df.index[mask][0]
    target_metadata = _metadata_df.iloc[target_idx]

    # Get the target flow's prediction to know what type of attack we're looking for
    target_pred = predict_proba(flow_id)
    target_class = target_pred['predicted_class']

    # If the target is BENIGN, we might still want to find similar attacks
    # but the directive says to find similar known attacks, so we'll look for
    # flows with the same predicted class (excluding BENIGN if we want actual attacks)

    # Find all flows with the same predicted class (or same label if available)
    similar_flows = []

    # Get predicted class for all flows (this could be slow, so we'll optimize by
    # only checking flows that are likely to be attacks if the target is an attack)
    if target_class != 'BENIGN':
        # If target is an attack, look for other flows predicted as the same attack type
        # We'll sample a subset for efficiency if the dataset is large
        sample_size = min(1000, len(_metadata_df))  # Limit sample size for performance
        if len(_metadata_df) > sample_size:
            # Stratified sampling to get representative attack flows
            attack_mask = _metadata_df['Label'] != 'BENIGN' if 'Label' in _metadata_df.columns else None
            if attack_mask is not None and attack_mask.any():
                # Sample from attack flows
                attack_flows = _metadata_df[attack_mask]
                if len(attack_flows) > sample_size:
                    sample_indices = attack_flows.sample(n=sample_size, random_state=42).index
                else:
                    sample_indices = attack_flows.index
            else:
                # Fallback to random sample
                sample_indices = _metadata_df.sample(n=sample_size, random_state=42).index
        else:
            sample_indices = _metadata_df.index

        # Check each sampled flow
        for idx in sample_indices:
            row = _metadata_df.loc[idx]
            flow_id_candidate = row['flow_id']

            # Skip the target flow itself
            if flow_id_candidate == flow_id_numeric:
                continue

            # Get prediction for this flow
            try:
                candidate_pred = predict_proba(flow_id_candidate)
                if candidate_pred['predicted_class'] == target_class:
                    # Flows are similar if they have the same predicted class
                    # Calculate feature similarity (we can use the model features for simplicity)
                    target_features = _get_model_features_for_flow_id(flow_id)
                    candidate_features = _get_model_features_for_flow_id(flow_id_candidate)

                    if not target_features.empty and not candidate_features.empty:
                        # Calculate similarity based on feature vectors (cosine similarity)
                        target_vec = target_features.iloc[0].values
                        candidate_vec = candidate_features.iloc[0].values

                        # Normalize vectors
                        target_norm = np.linalg.norm(target_vec)
                        candidate_norm = np.linalg.norm(candidate_vec)

                        if target_norm > 0 and candidate_norm > 0:
                            similarity = np.dot(target_vec, candidate_vec) / (target_norm * candidate_norm)
                        else:
                            similarity = 0.0

                        similar_flows.append({
                            'flow_id': int(flow_id_candidate),
                            'similarity_score': float(similarity),
                            'predicted_class': candidate_pred['predicted_class'],
                            'confidence': candidate_pred['confidence'],
                            'source_ip': str(row.get('Source IP', '')),
                            'source_port': int(row.get('Source Port', 0)) if pd.notna(row.get('Source Port')) else None,
                            'dest_ip': str(row.get('Destination IP', '')),
                            'dest_port': int(row.get('Destination Port', 0)) if pd.notna(row.get('Destination Port')) else None,
                            'protocol': str(row.get('Protocol', '')),
                            'timestamp': str(row.get('Timestamp', '')) if pd.notna(row.get('Timestamp')) else None
                        })
            except Exception as e:
                logger.warning(f"Error checking flow {flow_id_candidate}: {e}")
                continue
    else:
        # If target is BENIGN, we'll look for flows that are attacks (any non-BENIGN class)
        # This is useful for investigating why a benign flow might be suspicious
        sample_size = min(500, len(_metadata_df))
        if len(_metadata_df) > sample_size:
            sample_indices = _metadata_df.sample(n=sample_size, random_state=42).index
        else:
            sample_indices = _metadata_df.index

        for idx in sample_indices:
            row = _metadata_df.loc[idx]
            flow_id_candidate = row['flow_id']

            # Skip the target flow itself and benign flows
            if flow_id_candidate == flow_id_numeric:
                continue

            # Check if this flow is predicted as an attack
            try:
                candidate_pred = predict_proba(flow_id_candidate)
                if candidate_pred['predicted_class'] != 'BENIGN':
                    similar_flows.append({
                        'flow_id': int(flow_id_candidate),
                        'similarity_score': candidate_pred['confidence'],  # Use confidence as similarity
                        'predicted_class': candidate_pred['predicted_class'],
                        'confidence': candidate_pred['confidence'],
                        'source_ip': str(row.get('Source IP', '')),
                        'source_port': int(row.get('Source Port', 0)) if pd.notna(row.get('Source Port')) else None,
                        'dest_ip': str(row.get('Destination IP', '')),
                        'dest_port': int(row.get('Destination Port', 0)) if pd.notna(row.get('Destination Port')) else None,
                        'protocol': str(row.get('Protocol', '')),
                        'timestamp': str(row.get('Timestamp', '')) if pd.notna(row.get('Timestamp')) else None
                    })
            except Exception as e:
                logger.warning(f"Error checking flow {flow_id_candidate}: {e}")
                continue

    # Sort by similarity score (descending) and take top k
    similar_flows.sort(key=lambda x: x['similarity_score'], reverse=True)
    result = similar_flows[:k]

    logger.info(f"Found {len(result)} similar known attacks for flow {flow_id}")
    return result

def lookup_attack_pattern(label: str) -> Dict[str, Any]:
    """
    Look up information about an attack pattern.

    Args:
        label: The attack label to look up

    Returns:
        Dictionary with attack pattern information
    """
    logger.info(f"Looking up attack pattern for label: {label}")

    # Normalize the label to match our labeling convention
    from cyberagent.data_loader import normalize_label
    normalized_label = normalize_label(label)

    # Check if we have label information in features dataframe (not metadata)
    # The Label column is in features dataframe, not metadata
    if _features_df_full is None or 'Label' not in _features_df_full.columns:
        # If we don't have labels, return generic information
        return {
            'label': label,
            'normalized_label': normalized_label,
            'category': 'Unknown',
            'severity': 'Medium',
            'typical_ports': [],
            'protocols': [],
            'mitre_technique': 'Not available',
            'description': f"Attack pattern information for {label} is not available in the dataset."
        }

    # Find flows with this label in features dataframe
    label_mask = _features_df_full['Label'] == normalized_label
    if not label_mask.any():
        # Try without normalization in case the label is already normalized
        label_mask = _features_df_full['Label'] == label
        if not label_mask.any():
            return {
                'label': label,
                'normalized_label': normalized_label,
                'category': 'Unknown',
                'severity': 'Medium',
                'typical_ports': [],
                'protocols': [],
                'mitre_technique': 'Not available',
                'description': f"Attack pattern {label} not found in dataset."
            }

    # Get statistics for this attack type
    label_flows = _features_df_full[label_mask]

    # Extract common characteristics from features dataframe (has Destination Port and Protocol)
    if _features_df_full is not None and 'flow_id' in _features_df_full.columns:
        label_flow_ids = label_flows['flow_id'].tolist()
        feature_flows = _features_df_full[_features_df_full['flow_id'].isin(label_flow_ids)]
        # Destination Port and Protocol are in features
        src_ports = pd.Series([], dtype=int)  # Not in features, would need metadata
        dst_ports = feature_flows['Destination Port'].dropna().astype(int) if 'Destination Port' in feature_flows.columns else pd.Series([], dtype=int)
        protocols = feature_flows['Protocol'].dropna().unique()
    else:
        src_ports = pd.Series([], dtype=int)
        dst_ports = pd.Series([], dtype=int)
        protocols = []

    # Determine most common ports and protocols
    typical_src_ports = src_ports.value_counts().head(5).index.tolist() if len(src_ports) > 0 else []
    typical_dst_ports = dst_ports.value_counts().head(5).index.tolist() if len(dst_ports) > 0 else []
    typical_protocols = [str(p) for p in protocols] if len(protocols) > 0 else []

    # Map to MITRE ATT&CK (simplified mapping)
    mitre_mapping = {
        'DDoS': 'T1498',  # Network Denial of Service
        'DoS Hulk': 'T1498',
        'DoS GoldenEye': 'T1498',
        'DoS slowloris': 'T1498',
        'DoS Slowhttptest': 'T1498',
        'PortScan': 'T1046',  # Network Service Scanning
        'FTP-Patator': 'T1021.001',  # Remote Services: FTP
        'SSH-Patator': 'T1021.004',  # Remote Services: SSH
        'Web Attack': 'T1190',  # Exploit Public-Facing Application
        'Bot': 'T1059.003',  # Command and Scripting Interpreter: Windows Command Shell
        'Infiltration': 'T1071',  # Application Layer Protocol
        'Heartbleed': 'T1190',  # Exploit Public-Facing Application (Heartbleed)
        'BENIGN': 'None'  # Not an attack
    }

    mitre_technique = mitre_mapping.get(normalized_label, 'Not available')

    # Determine severity based on attack type
    severity_mapping = {
        'DDoS': 'High',
        'DoS Hulk': 'High',
        'DoS GoldenEye': 'High',
        'DoS slowloris': 'Medium',
        'DoS Slowhttptest': 'Medium',
        'PortScan': 'Low',
        'FTP-Patator': 'Medium',
        'SSH-Patator': 'Medium',
        'Web Attack': 'High',
        'Bot': 'High',
        'Infiltration': 'High',
        'Heartbleed': 'High',
        'BENIGN': 'None'
    }

    severity = severity_mapping.get(normalized_label, 'Medium')

    result = {
        'label': label,
        'normalized_label': normalized_label,
        'description': f"Attack pattern: {normalized_label}",
        'category': 'Attack' if normalized_label != 'BENIGN' else 'Benign',
        'severity': severity,
        'typical_source_ports': typical_src_ports,
        'typical_destination_ports': typical_dst_ports,
        'typical_ports': list(set(typical_src_ports + typical_dst_ports))[:10],  # Combined top 10
        'protocols': typical_protocols,
        'mitre_technique': mitre_technique,
        'sample_size': int(len(label_flows)),
        'first_seen': str(label_flows['Timestamp'].min()) if 'Timestamp' in label_flows.columns and not label_flows['Timestamp'].isna().all() else None,
        'last_seen': str(label_flows['Timestamp'].max()) if 'Timestamp' in label_flows.columns and not label_flows['Timestamp'].isna().all() else None
    }

    logger.info(f"Attack pattern lookup completed for {label}")
    return result

# For backward compatibility and easy import
def get_investigation_tools():
    """Return a dictionary of all investigation tools."""
    return {
        'predict_proba': predict_proba,
        'explain_flow': explain_flow,
        'find_related_flows': find_related_flows,
        'similar_known_attacks': similar_known_attacks,
        'lookup_attack_pattern': lookup_attack_pattern
    }

if __name__ == "__main__":
    # Simple test
    logger.info("Testing investigation tools...")
    try:
        # Test with a sample flow ID (assuming flow IDs start from 0)
        test_flow_id = 0
        print(f"Testing predict_proba for flow {test_flow_id}:")
        result = predict_proba(test_flow_id)
        print(f"  Result: {result}")

        print(f"Testing explain_flow for flow {test_flow_id}:")
        result = explain_flow(test_flow_id)
        print(f"  Top features: {len(result.get('top_features', []))}")

        print(f"Testing find_related_flows for flow {test_flow_id}:")
        result = find_related_flows(test_flow_id)
        print(f"  Found {len(result)} related flows")

        print(f"Testing similar_known_attacks for flow {test_flow_id}:")
        result = similar_known_attacks(test_flow_id, k=3)
        print(f"  Found {len(result)} similar attacks")

        print(f"Testing lookup_attack_pattern for 'DDoS':")
        result = lookup_attack_pattern('DDoS')
        print(f"  Result: {result.get('description', 'No description')}")

        print("All tests completed successfully!")
    except Exception as e:
        logger.error(f"Error in investigation tools test: {e}")
        print(f"Test failed with error: {e}")