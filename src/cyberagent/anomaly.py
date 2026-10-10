"""
Anomaly detection module for CyberAgent.
Implements Isolation Forest for unknown attack detection.
"""
import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Tuple, Optional
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cyberagent.config import config
from cyberagent.logging_setup import logger

def train_isolation_forest(
    X_train: pd.DataFrame,
    contamination: Optional[float] = None,
    random_state: Optional[int] = None,
    n_estimators: Optional[int] = None,
    max_samples: str = 'auto'
) -> IsolationForest:
    """
    Train Isolation Forest on benign-only data for anomaly detection.

    Args:
        X_train: Training features (should be benign-only or mostly benign)
        contamination: Expected proportion of outliers. If None, uses config.
        random_state: Random seed. If None, uses config.
        n_estimators: Number of base estimators. If None, uses config.
        max_samples: Number of samples to draw for each base estimator.

    Returns:
        Trained IsolationForest model
    """
    if contamination is None:
        contamination = config.get("anomaly.contamination", 0.1)
    if random_state is None:
        random_state = config.get("seed", 42)
    if n_estimators is None:
        n_estimators = config.get("anomaly.n_estimators", 100)

    logger.info(f"Training Isolation Forest with contamination={contamination}, n_estimators={n_estimators}")

    # Scale the data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # Train Isolation Forest
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
        max_samples=max_samples,
        n_jobs=-1
    )
    model.fit(X_train_scaled)

    logger.info(f"Isolation Forest training complete.")

    # Return both model and scaler for later use
    return model, scaler

def predict_anomaly(
    model: IsolationForest,
    scaler: StandardScaler,
    X: pd.DataFrame
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Predict anomaly scores and labels.

    Args:
        model: Trained IsolationForest model
        scaler: Fitted StandardScaler
        X: Features to predict on

    Returns:
        Tuple of (anomaly_scores, anomaly_labels)
        where anomaly_labels: -1 for outliers, 1 for inliers
    """
    # Scale the data
    X_scaled = scaler.transform(X)

    # Predict anomaly scores: the lower, the more abnormal
    anomaly_scores = model.decision_function(X_scaled)
    # Predict labels: -1 for outliers, 1 for inliers
    anomaly_labels = model.predict(X_scaled)

    return anomaly_scores, anomaly_labels

def save_anomaly_model(
    model: IsolationForest,
    scaler: StandardScaler,
    model_dir: str = "models"
) -> None:
    """
    Save Isolation Forest model and scaler to disk.

    Args:
        model: Trained IsolationForest model
        scaler: Fitted StandardScaler
        model_dir: Directory to save the model
    """
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    # Save model
    model_file = model_path / "isolation_forest.joblib"
    joblib.dump(model, model_file)
    logger.info(f"Saved Isolation Forest model to {model_file}")

    # Save scaler
    scaler_file = model_path / "isolation_forest_scaler.joblib"
    joblib.dump(scaler, scaler_file)
    logger.info(f"Saved Isolation Forest scaler to {scaler_file}")

def load_anomaly_model(
    model_dir: str = "models"
) -> Tuple[IsolationForest, StandardScaler]:
    """
    Load Isolation Forest model and scaler from disk.

    Args:
        model_dir: Directory where the model is saved

    Returns:
        Tuple of (model, scaler)
    """
    model_path = Path(model_dir)

    # Load model
    model_file = model_path / "isolation_forest.joblib"
    if not model_file.exists():
        raise FileNotFoundError(f"Isolation Forest model not found: {model_file}")
    model = joblib.load(model_file)

    # Load scaler
    scaler_file = model_path / "isolation_forest_scaler.joblib"
    if not scaler_file.exists():
        raise FileNotFoundError(f"Isolation Forest scaler not found: {scaler_file}")
    scaler = joblib.load(scaler_file)

    logger.info(f"Loaded Isolation Forest model and scaler from {model_dir}")

    return model, scaler

def main():
    """Main function for demonstration."""
    logger.info("Starting Isolation Forest anomaly detection demo...")

    # In a real scenario, you would load and preprocess data
    # For this example, we'll use synthetic data
    from cyberagent.data_loader import load_data
    from cyberagent.preprocess import example_preprocessing_pipeline

    # Run example preprocessing to get data
    data_dict = example_preprocessing_pipeline()

    # Extract data
    X_train = data_dict['X_train']
    y_train = data_dict['y_train']

    # For Isolation Forest, we want to train on benign-only data
    # Let's filter the training data to only benign samples
    benign_mask = (y_train == 'BENIGN')
    X_train_benign = X_train[benign_mask]

    logger.info(f"Training Isolation Forest on {len(X_train_benign)} benign samples")

    # Train Isolation Forest
    model, scaler = train_isolation_forest(
        X_train_benign,
        contamination=0.1,  # Expect 10% anomalies in the data we will test on
        random_state=42,
        n_estimators=100
    )

    # Save the model
    save_anomaly_model(model, scaler)

    # Test on the full training set (including anomalies)
    logger.info("Testing on full training set...")
    anomaly_scores, anomaly_labels = predict_anomaly(model, scaler, X_train)

    # Convert anomaly_labels: -1 -> outlier (anomaly), 1 -> inlier (normal)
    # We'll consider outliers as detected anomalies
    n_anomalies = np.sum(anomaly_labels == -1)
    n_total = len(anomaly_labels)

    logger.info(f"Detected {n_anomalies} anomalies out of {n_total} samples ({n_anomalies/n_total*100:.2f}%)")

    # Also check how many of the actual non-benign samples were detected
    non_benign_mask = (y_train != 'BENIGN')
    detected_as_anomaly = (anomaly_labels == -1)
    true_positives = np.sum(non_benign_mask & detected_as_anomaly)
    false_positives = np.sum(~non_benign_mask & detected_as_anomaly)
    false_negatives = np.sum(non_benign_mask & ~detected_as_anomaly)

    logger.info(f"True positives: {true_positives}")
    logger.info(f"False positives: {false_positives}")
    logger.info(f"False negatives: {false_negatives}")

    if np.sum(non_benign_mask) > 0:
        recall = true_positives / np.sum(non_benign_mask)
        logger.info(f"Recall (for non-benign): {recall:.4f}")
    if (true_positives + false_positives) > 0:
        precision = true_positives / (true_positives + false_positives)
        logger.info(f"Precision: {precision:.4f}")

    logger.info("Isolation Forest demo complete.")

    return model, scaler

if __name__ == "__main__":
    main()