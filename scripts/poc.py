"""
Proof of Concept script for CyberAgent.
Demonstrates detector and agent tool-calling end to end.
"""
import sys
import os
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import os
from pathlib import Path
import json
from src.cyberagent.config import config
from src.cyberagent.logging_setup import logger
from src.cyberagent.data_loader import load_data, generate_synthetic_data
from scripts.reduce_dataset import reduce_dataset, save_reduced_dataset
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, classification_report
from sklearn.preprocessing import LabelEncoder

def train_lightgbm_model(X_train, y_train, X_val, y_val, feature_names):
    """
    Train a LightGBM model for the proof of concept.

    Args:
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        feature_names: List of feature names

    Returns:
        Trained LightGBM model
    """
    # Encode labels
    le = LabelEncoder()
    y_train_encoded = le.fit_transform(y_train)
    y_val_encoded = le.transform(y_val)

    # Create LightGBM datasets
    train_data = lgb.Dataset(X_train, label=y_train_encoded, feature_name=feature_names)
    val_data = lgb.Dataset(X_val, label=y_val_encoded, feature_name=feature_names, reference=train_data)

    # Set parameters
    params = {
        'objective': 'multiclass',
        'num_class': len(le.classes_),
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'seed': config.get('seed', 42)
    }

    # Train model
    logger.info("Training LightGBM model...")
    model = lgb.train(
        params,
        train_data,
        num_boost_round=100,
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(10), lgb.log_evaluation(10)]
    )

    return model, le

def _convert_to_native(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    """
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_to_native(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_native(item) for item in obj]
    else:
        return obj

def predict_proba_tool(flow_id: int, model, features_df: pd.DataFrame, label_encoder) -> dict:
    """
    Tool to predict probabilities for a given flow_id.

    Args:
        flow_id: Integer flow ID
        model: Trained LightGBM model
        features_df: DataFrame with features
        label_encoder: Fitted label encoder

    Returns:
        Dictionary with prediction results
    """
    # Get features for the flow_id
    if flow_id not in features_df['flow_id'].values:
        return {"error": f"Flow ID {flow_id} not found"}

    # Get feature row
    feature_row = features_df[features_df['flow_id'] == flow_id].drop(columns=['flow_id', 'Label'], errors='ignore')

    # Make prediction
    pred_proba = model.predict(feature_row, num_iteration=model.best_iteration)
    pred_class_idx = np.argmax(pred_proba[0])
    pred_class = label_encoder.classes_[pred_class_idx]
    confidence = float(pred_proba[0][pred_class_idx])

    result = {
        "flow_id": flow_id,
        "predicted_class": pred_class,
        "confidence": confidence,
        "class_probabilities": {
            class_name: float(prob)
            for class_name, prob in zip(label_encoder.classes_, pred_proba[0])
        }
    }

    # Convert numpy types to native Python types
    return _convert_to_native(result)

def explain_flow_tool(flow_id: int, model, features_df: pd.DataFrame, feature_names: list) -> dict:
    """
    Tool to explain a prediction using feature values (simplified SHAP-like explanation).

    Args:
        flow_id: Integer flow ID
        model: Trained LightGBM model
        features_df: DataFrame with features
        feature_names: List of feature names

    Returns:
        Dictionary with explanation
    """
    # Get features for the flow_id
    if flow_id not in features_df['flow_id'].values:
        return {"error": f"Flow ID {flow_id} not found"}

    # Get feature row
    feature_row = features_df[features_df['flow_id'] == flow_id].drop(columns=['flow_id', 'Label'], errors='ignore')
    feature_values = feature_row.iloc[0].to_dict()

    # Get feature importance from model (simplified explanation)
    # In a real implementation, we would use SHAP values
    feature_importance = model.feature_importance(importance_type='gain')
    feature_importance_dict = dict(zip(feature_names, feature_importance))

    # Sort by importance
    sorted_features = sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True)

    # Get top 5 features
    top_features = sorted_features[:5]

    explanation = []
    for feat_name, importance in top_features:
        if feat_name in feature_values:
            explanation.append({
                "feature": feat_name,
                "value": float(feature_values[feat_name]),
                "importance": float(importance)
            })

    result = {
        "flow_id": flow_id,
        "explanation": explanation
    }

    # Convert numpy types to native Python types
    return _convert_to_native(result)

def find_related_flows_tool(flow_id: int, features_df: pd.DataFrame, metadata_df: pd.DataFrame) -> dict:
    """
    Tool to find related flows based on common characteristics.

    Args:
        flow_id: Integer flow ID
        features_df: DataFrame with features
        metadata_df: DataFrame with metadata

    Returns:
        Dictionary with related flows information
    """
    # Get metadata for the flow_id
    if flow_id not in metadata_df['flow_id'].values:
        return {"error": f"Flow ID {flow_id} not found in metadata"}

    # Get features for the flow_id
    if flow_id not in features_df['flow_id'].values:
        return {"error": f"Flow ID {flow_id} not found in features"}

    flow_metadata = metadata_df[metadata_df['flow_id'] == flow_id].iloc[0]
    flow_features = features_df[features_df['flow_id'] == flow_id].iloc[0]

    source_ip = flow_metadata['Source IP']
    dest_port = flow_features['Destination Port']

    # Find flows with same Source IP (from metadata_df)
    related_same_ip = metadata_df[
        (metadata_df['Source IP'] == source_ip) &
        (metadata_df['flow_id'] != flow_id)
    ]

    # Find flows with same Destination Port: get flow_ids from features_df with that port, then get their metadata
    same_port_flow_ids = features_df[
        features_df['Destination Port'] == dest_port
    ]['flow_id']
    related_same_port = metadata_df[
        metadata_df['flow_id'].isin(same_port_flow_ids) &
        (metadata_df['flow_id'] != flow_id)
    ]

    # Combine and limit results
    related_flow_ids = list(set(
        list(related_same_ip['flow_id'].head(10)) +
        list(related_same_port['flow_id'].head(10))
    ))[:10]

    # Get details for related flows
    related_details = []
    for fid in related_flow_ids:
        fid_metadata = metadata_df[metadata_df['flow_id'] == fid].iloc[0]
        fid_features = features_df[features_df['flow_id'] == fid].iloc[0]

        related_details.append({
            "flow_id": int(fid),
            "source_ip": str(fid_metadata['Source IP']),
            "dest_ip": str(fid_metadata['Destination IP']),
            "dest_port": int(fid_features['Destination Port']) if 'Destination Port' in fid_features else None,
            "label": str(fid_metadata.get('Label', 'Unknown'))
        })

    result = {
        "flow_id": flow_id,
        "source_ip": str(source_ip),
        "dest_port": int(dest_port) if 'Destination Port' in flow_features else None,
        "related_flows": related_details,
        "count_same_ip": len(related_same_ip),
        "count_same_port": len(related_same_port)
    }

    # Convert numpy types to native Python types
    return _convert_to_native(result)

def mock_agent_investigation(flow_id: int, model, features_df: pd.DataFrame, metadata_df: pd.DataFrame, label_encoder, feature_names: list) -> dict:
    """
    Mock agent investigation that uses tools in a fixed order.

    Args:
        flow_id: Integer flow ID to investigate
        model: Trained LightGBM model
        features_df: DataFrame with features
        metadata_df: DataFrame with metadata
        label_encoder: Fitted label encoder
        feature_names: List of feature names

    Returns:
        Dictionary with investigation report
    """
    logger.info(f"Starting mock agent investigation for flow_id {flow_id}")

    # Step 1: Get prediction
    prediction_result = predict_proba_tool(flow_id, model, features_df, label_encoder)
    if "error" in prediction_result:
        return {"error": prediction_result["error"]}

    predicted_class = prediction_result["predicted_class"]
    confidence = prediction_result["confidence"]

    logger.info(f"Prediction: {predicted_class} (confidence: {confidence:.3f})")

    # Step 2: Get explanation
    explanation_result = explain_flow_tool(flow_id, model, features_df, feature_names)

    # Step 3: Find related flows
    related_result = find_related_flows_tool(flow_id, features_df, metadata_df)

    # Step 4: Determine verdict and severity
    # Simple logic: if confidence is high and prediction is not BENIGN, consider it malicious
    if confidence >= 0.7 and predicted_class != 'BENIGN':
        verdict = "MALICIOUS"
        severity = "HIGH" if confidence >= 0.9 else "MEDIUM"
    elif confidence < 0.5:
        verdict = "UNCERTAIN"
        severity = "LOW"
    else:
        verdict = "BENIGN" if predicted_class == 'BENIGN' else "SUSPICIOUS"
        severity = "LOW"

    # Determine if human review is needed
    needs_human_review = (
        confidence < 0.6 or  # Low confidence
        (predicted_class != 'BENIGN' and confidence < 0.8)  # Medium confidence attack
    )

    # Create evidence list
    evidence = []

    # Add prediction evidence
    evidence.append({
        "claim": f"The ML model predicts flow {flow_id} is {predicted_class} with {confidence:.1%} confidence",
        "source_tool": "predict_proba",
        "source_value": json.dumps(prediction_result)
    })

    # Add explanation evidence
    if "explanation" in explanation_result and explanation_result["explanation"]:
        top_feature = explanation_result["explanation"][0]
        evidence.append({
            "claim": f"The most important feature is {top_feature['feature']} with value {top_feature['value']:.2f}",
            "source_tool": "explain_flow",
            "source_value": json.dumps(explanation_result)
        })

    # Add related flows evidence
    if "related_flows" in related_result and related_result["related_flows"]:
        related_count = len(related_result["related_flows"])
        evidence.append({
            "claim": f"Found {related_count} related flows sharing source IP or destination port",
            "source_tool": "find_related_flows",
            "source_value": json.dumps(related_result)
        })

    # Create report
    report = {
        "flow_id": flow_id,
        "predicted_class": predicted_class,
        "verdict": verdict,
        "severity": severity,
        "confidence": confidence,
        "needs_human_review": needs_human_review,
        "evidence": evidence,
        "mitre_technique": "TBA",  # Would be filled from MITRE map in real implementation
        "recommended_actions": [
            "Monitor source IP for additional suspicious activity",
            "Check destination port for known vulnerabilities"
        ] if verdict in ["MALICIOUS", "SUSPICIOUS"] else [],
        "limitations": [
            "Explanation is feature importance-based, not SHAP values",
            "Related flows analysis is simplified"
        ]
    }

    # Convert numpy types to native Python types in the entire report
    report = _convert_to_native(report)

    logger.info(f"Investigation complete. Verdict: {verdict}, Severity: {severity}")
    return report

def main():
    """Main proof of concept function."""
    logger.info("Starting CyberAgent Proof of Concept")

    # Generate synthetic data
    logger.info("Generating synthetic data for PoC...")
    features_df, metadata_df = load_data(synthetic=True)
    logger.info(f"Generated {len(features_df)} samples")

    # Show label distribution
    if 'Label' in metadata_df.columns:
        logger.info(f"Label distribution:\n{metadata_df['Label'].value_counts()}")

    # For PoC, we'll use a small subset to keep things fast
    # But we want to ensure we have some attack samples
    # Let's reduce the dataset with small caps
    reduced_features_df, reduced_metadata_df = reduce_dataset(
        features_df, metadata_df,
        benign_cap=200,
        attack_cap=50,
        seed=42
    )

    logger.info(f"Reduced dataset: {len(reduced_features_df)} samples")

    # Prepare features and labels for training
    # Ensure Label is in features_df for training
    if 'Label' not in reduced_features_df.columns:
        reduced_features_df = reduced_features_df.merge(
            reduced_metadata_df[['flow_id', 'Label']],
            on='flow_id',
            how='left'
        )

    # Separate features and labels
    feature_columns = [col for col in reduced_features_df.columns
                      if col not in ['flow_id', 'Label']]
    X = reduced_features_df[feature_columns]
    y = reduced_features_df['Label']

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=config.get('seed', 42), stratify=y
    )

    # Further split training data for validation
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=config.get('seed', 42), stratify=y_train
    )

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Validation set: {len(X_val)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Train LightGBM model
    model, label_encoder = train_lightgbm_model(X_train, y_train, X_val, y_val, feature_columns)

    # Evaluate on test set
    logger.info("Evaluating model on test set...")
    X_test_array = X_test.values
    y_test_encoded = label_encoder.transform(y_test)
    test_pred_proba = model.predict(X_test_array, num_iteration=model.best_iteration)
    test_pred = np.argmax(test_pred_proba, axis=1)
    test_pred_labels = label_encoder.inverse_transform(test_pred)

    # Calculate macro-F1
    macro_f1 = f1_score(y_test, test_pred_labels, average='macro')
    logger.info(f"Test Macro-F1: {macro_f1:.4f}")

    # Show classification report
    logger.info("Classification Report:")
    logger.info("\n" + classification_report(y_test, test_pred_labels))

    # Select a few interesting flows for agent investigation
    # Let's pick some attacks and some benign samples
    test_with_pred = X_test.copy()
    test_with_pred['flow_id'] = reduced_metadata_df[
        reduced_metadata_df['flow_id'].isin(X_test.index)
    ]['flow_id'].values
    test_with_pred['true_label'] = y_test.values
    test_with_pred['pred_label'] = test_pred_labels

    # Find some attack samples that were correctly predicted
    attack_samples = test_with_pred[
        (test_with_pred['true_label'] != 'BENIGN') &
        (test_with_pred['true_label'] == test_with_pred['pred_label'])
    ]

    # Find some benign samples
    benign_samples = test_with_pred[
        test_with_pred['true_label'] == 'BENIGN'
    ]

    logger.info(f"Found {len(attack_samples)} correctly predicted attack samples")
    logger.info(f"Found {len(benign_samples)} benign samples")

    # Run agent investigation on a few samples
    investigation_results = []

    # Investigate up to 3 attack samples
    for i in range(min(3, len(attack_samples))):
        sample = attack_samples.iloc[i]
        flow_id = sample['flow_id']
        logger.info(f"\n--- Investigating attack sample {i+1} (flow_id: {flow_id}) ---")
        report = mock_agent_investigation(
            flow_id, model, reduced_features_df, reduced_metadata_df,
            label_encoder, feature_columns
        )
        investigation_results.append(report)

        # Print report summary
        logger.info(f"Verdict: {report['verdict']}")
        logger.info(f"Severity: {report['severity']}")
        logger.info(f"Confidence: {report['confidence']:.3f}")
        logger.info(f"Needs Human Review: {report['needs_human_review']}")
        logger.info(f"Evidence count: {len(report['evidence'])}")

    # Investigate up to 2 benign samples
    for i in range(min(2, len(benign_samples))):
        sample = benign_samples.iloc[i]
        flow_id = sample['flow_id']
        logger.info(f"\n--- Investigating benign sample {i+1} (flow_id: {flow_id}) ---")
        report = mock_agent_investigation(
            flow_id, model, reduced_features_df, reduced_metadata_df,
            label_encoder, feature_columns
        )
        investigation_results.append(report)

        # Print report summary
        logger.info(f"Verdict: {report['verdict']}")
        logger.info(f"Severity: {report['severity']}")
        logger.info(f"Confidence: {report['confidence']:.3f}")
        logger.info(f"Needs Human Review: {report['needs_human_review']}")
        logger.info(f"Evidence count: {len(report['evidence'])}")

    # Save investigation results
    results_dir = Path("results/agent_logs")
    results_dir.mkdir(parents=True, exist_ok=True)

    results_file = results_dir / "poc_investigations.json"
    with open(results_file, 'w') as f:
        json.dump(investigation_results, f, indent=2)

    logger.info(f"\nSaved investigation results to {results_file}")

    # Print final summary
    logger.info("\n" + "="*50)
    logger.info("PROOF OF CONCEPT COMPLETE")
    logger.info("="*50)
    logger.info(f"Dataset size: {len(reduced_features_df)} samples")
    logger.info(f"Model Macro-F1: {macro_f1:.4f}")
    logger.info(f"Investigations performed: {len(investigation_results)}")
    logger.info(f"Results saved to: {results_file}")
    logger.info("="*50)

    return macro_f1, investigation_results

if __name__ == "__main__":
    macro_f1, results = main()
    logger.info("PoC finished successfully!")