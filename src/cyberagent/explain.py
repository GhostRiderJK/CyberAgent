"""
Explainability module for CyberAgent.
Handles SHAP explanations for tree-based models.
"""
import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import shap
from src.cyberagent.config import config
from src.cyberagent.logging_setup import logger

def explain_model(model, X_background: pd.DataFrame, X_to_explain: pd.DataFrame):
    """
    Create a SHAP explainer and explain the model predictions.

    Args:
        model: Trained tree-based model (LightGBM, XGBoost, RandomForest)
        X_background: Background dataset for SHAP (typically training data)
        X_to_explain: Instances to explain

    Returns:
        Tuple of (explainer, shap_values)
    """
    logger.info(f"Creating SHAP explainer for {type(model).__name__}")

    # Choose the appropriate explainer based on model type
    if str(type(model)).find('LGBM') != -1:
        # LightGBM model
        explainer = shap.TreeExplainer(model)
    elif str(type(model)).find('XGB') != -1:
        # XGBoost model
        explainer = shap.TreeExplainer(model)
    elif str(type(model)).find('RandomForest') != -1:
        # Random Forest model
        explainer = shap.TreeExplainer(model)
    else:
        # Fallback to KernelExplainer (slower)
        logger.warning(f"Using KernelExplainer for {type(model).__name__} (may be slow)")
        explainer = shap.KernelExplainer(model.predict, X_background)

    # Calculate SHAP values
    shap_values = explainer.shap_values(X_to_explain)

    # For multiclass, shap_values is a list of arrays (one per class)
    # For binary classification, shap_values is an array of shape (n_samples, n_features)
    # We return the explainer and the raw shap_values; the caller can handle multiclass
    return explainer, shap_values

def explain_instance(model, X_background: pd.DataFrame, instance: pd.DataFrame,
                     instance_index: int = 0) -> Tuple[np.ndarray, List[str]]:
    """
    Explain a single instance and return the top features.

    Args:
        model: Trained tree-based model
        X_background: Background dataset for SHAP
        instance: Single instance to explain (DataFrame with one row)
        instance_index: Index of the instance in the instance DataFrame (default 0)

    Returns:
        Tuple of (shap_values_for_instance, feature_names)
    """
    # Ensure instance is a DataFrame with one row
    if isinstance(instance, pd.Series):
        instance = instance.to_frame().T

    # Get SHAP values
    explainer, shap_values = explain_model(model, X_background, instance)

    # For multiclass, we need to choose the class to explain
    # We'll use the model's prediction to choose the class
    if isinstance(shap_values, list):
        # Multiclass: shap_values is a list of arrays, one per class
        # Predict the class
        pred = model.predict(instance)
        # If the model has a label_encoder_ attribute (as we added in train.py for XGBoost and LightGBM), use it
        if hasattr(model, 'label_encoder_'):
            pred_class = model.label_encoder_.inverse_transform(pred)[0] if isinstance(pred, np.ndarray) else model.label_encoder_.inverse_transform([pred])[0]
        else:
            pred_class = pred[0] if isinstance(pred, np.ndarray) else pred
        # Get the index of the predicted class
        # For tree-based models, we can get the classes from the model
        if hasattr(model, 'classes_'):
            classes = model.classes_
        else:
            # Fallback: use the unique values in the background data
            # But note: we don't have the labels in X_background. We'll use the model's classes_ if available, else we cannot map.
            # Since we have the label_encoder_ in the model for XGBoost and LightGBM, we should have classes_ as well.
            # If not, we'll try to get the classes from the label_encoder_
            if hasattr(model, 'label_encoder_'):
                classes = model.label_encoder_.classes_
            else:
                # Last resort: use the unique values in the background data (but we don't have labels)
                # This is a hack and may not be correct.
                classes = np.unique(X_background.iloc[:, 0])  # This is a hack, but we don't have the labels here
                # Actually, we don't have the labels in X_background. We'll skip this for now.
                # Instead, we'll return the shap_values for the first class and let the caller handle it.
                # This is a limitation of this function.
                # We'll return the shap_values for class 0.
                class_index = 0
                shap_vals = shap_values[0][instance_index]
                # Get feature names
                feature_names = list(X_background.columns)
                return shap_vals, feature_names
        # Get the index of the predicted class
        try:
            class_index = list(classes).index(pred_class)
        except ValueError:
            # If the predicted class is not in the list of classes, use the first class
            class_index = 0
        shap_vals = shap_values[class_index][instance_index]
    else:
        # Binary classification or regression
        shap_vals = shap_values[instance_index]

    # Get feature names
    feature_names = list(X_background.columns)

    # Ensure shap_vals is 1D
    if shap_vals.ndim > 1:
        shap_vals = shap_vals.ravel()

    return shap_vals, feature_names

def explain_instance_top_features(model, X_background: pd.DataFrame, instance: pd.DataFrame,
                                  top_k: int = 10, instance_index: int = 0) -> List[Dict[str, Any]]:
    """
    Explain a single instance and return the top k features by absolute SHAP value.

    Args:
        model: Trained tree-based model
        X_background: Background dataset for SHAP
        instance: Single instance to explain (DataFrame with one row)
        top_k: Number of top features to return
        instance_index: Index of the instance in the instance DataFrame (default 0)

    Returns:
        List of dictionaries with keys: 'feature', 'shap_value', 'value'
    """
    shap_vals, feature_names = explain_instance(model, X_background, instance, instance_index)

    # Get the feature values for the instance
    if isinstance(instance, pd.DataFrame):
        feature_values = instance.iloc[instance_index]
    else:
        feature_values = instance

    # Create list of feature contributions
    contributions = []
    for i, feature in enumerate(feature_names):
        # Get the feature value for the instance at position i
        if hasattr(feature_values, 'iloc'):
            # pandas Series or DataFrame
            value = float(feature_values.iloc[i]) if i < len(feature_values) else 0.0
        else:
            # numpy array or list
            value = float(feature_values[i]) if i < len(feature_values) else 0.0
        contributions.append({
            'feature': feature,
            'shap_value': float(shap_vals[i]),
            'value': value
        })

    # Sort by absolute SHAP value
    contributions.sort(key=lambda x: abs(x['shap_value']), reverse=True)

    # Return top k
    return contributions[:top_k]

def save_shap_explainer(explainer: shap.Explainer, filepath: str) -> None:
    """
    Save SHAP explainer to disk.

    Args:
        explainer: SHAP explainer object
        filepath: Path to save the explainer
    """
    # Note: SHAP objects are not directly serializable with joblib in all cases.
    # We'll save the underlying model and then recreate the explainer.
    # For TreeExplainer, we can save the model.
    # For simplicity, we'll save the model that the explainer wraps.
    # This is a hack. In a real implementation, we would use joblib to save the explainer.
    # But let's try to save the explainer directly.
    import joblib
    joblib.dump(explainer, filepath)
    logger.info(f"Saved SHAP explainer to {filepath}")

def load_shap_explainer(filepath: str) -> shap.Explainer:
    """
    Load SHAP explainer from disk.

    Args:
        filepath: Path to the saved explainer

    Returns:
        SHAP explainer object
    """
    import joblib
    explainer = joblib.load(filepath)
    logger.info(f"Loaded SHAP explainer from {filepath}")
    return explainer

def main():
    """Main function for demonstration."""
    logger.info("Starting SHAP explainability demo...")

    # In a real scenario, you would load a trained model and data
    # For this example, we'll use synthetic data and a dummy model
    from src.cyberagent.data_loader import load_data
    from src.cyberagent.preprocess import example_preprocessing_pipeline
    from src.cyberagent.train import train_lightgbm

    # Run example preprocessing to get data
    data_dict = example_preprocessing_pipeline()

    # Extract data
    X_train = data_dict['X_train']
    X_val = data_dict['X_val']
    y_train = data_dict['y_train']
    y_val = data_dict['y_val']

    logger.info(f"Data shapes - Train: {X_train.shape}, Val: {X_val.shape}")

    # Train a LightGBM model
    model = train_lightgbm(X_train, y_train, X_val, y_val)

    # Explain a few instances from the validation set
    logger.info("Explaining validation instances...")

    # We'll use the first 5 validation instances
    X_to_explain = X_val.head(5)

    # Get SHAP explanations
    explainer, shap_values = explain_model(model, X_train, X_to_explain)

    # For multiclass, we need to handle the shap_values appropriately
    # For simplicity, we'll just show the shape
    logger.info(f"SHAP values shape: {np.array(shap_values).shape if isinstance(shap_values, list) else shap_values.shape}")

    # Explain a single instance
    instance = X_val.iloc[0:1]  # First instance as DataFrame
    top_features = explain_instance_top_features(model, X_train, instance, top_k=5)

    logger.info(f"Top 5 features for instance 0:")
    for feat in top_features:
        logger.info(f"  {feat['feature']}: SHAP={feat['shap_value']:.4f}, value={feat['value']:.4f}")

    # Save the explainer
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    explainer_path = results_dir / "shap_explainer.joblib"
    save_shap_explainer(explainer, str(explainer_path))

    logger.info("SHAP explainability demo complete.")

if __name__ == "__main__":
    main()