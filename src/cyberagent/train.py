"""
Training module for CyberAgent.
Handles model training, evaluation, and tracking.
"""
import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import time
import joblib
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
import lightgbm as lgb
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
from cyberagent.config import config
from cyberagent.logging_setup import logger
import mlflow
import mlflow.sklearn
import mlflow.lightgbm

def train_logistic_regression(X_train, y_train, X_val, y_val, class_weight=None) -> LogisticRegression:
    """Train Logistic Regression model."""
    logger.info("Training Logistic Regression...")
    start_time = time.time()

    model = LogisticRegression(
        random_state=config.get("seed", 42),
        max_iter=1000,
        class_weight=class_weight,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Validate
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    logger.info(f"Logistic Regression validation macro-F1: {val_f1:.4f}")

    train_time = time.time() - start_time
    logger.info(f"Logistic Regression training time: {train_time:.2f}s")

    return model

def train_random_forest(X_train, y_train, X_val, y_val, class_weight=None) -> RandomForestClassifier:
    """Train Random Forest model."""
    logger.info("Training Random Forest...")
    start_time = time.time()

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=config.get("seed", 42),
        class_weight=class_weight,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Validate
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    logger.info(f"Random Forest validation macro-F1: {val_f1:.4f}")

    train_time = time.time() - start_time
    logger.info(f"Random Forest training time: {train_time:.2f}s")

    return model

def train_xgboost(X_train, y_train, X_val, y_val, class_weight=None) -> xgb.XGBClassifier:
    """Train XGBoost model."""
    logger.info("Training XGBoost...")
    start_time = time.time()

    # XGBoost requires numeric labels, so we encode the string labels
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_val_enc = le.transform(y_val)

    # Convert class_weight to scale_pos_weight for binary, but we'll use it for multiclass via sample_weight
    # For simplicity, we'll not use class_weight directly in XGBoost for multiclass here
    model = xgb.XGBClassifier(
        n_estimators=100,
        random_state=config.get("seed", 42),
        n_jobs=-1,
        eval_metric='mlogloss'
    )
    model.fit(
        X_train, y_train_enc,
        eval_set=[(X_val, y_val_enc)],
        verbose=False
    )
    # Store the label encoder for inverse transformation during evaluation
    model.label_encoder_ = le

    # Validate
    y_val_pred_enc = model.predict(X_val)
    y_val_pred = le.inverse_transform(y_val_pred_enc)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    logger.info(f"XGBoost validation macro-F1: {val_f1:.4f}")

    train_time = time.time() - start_time
    logger.info(f"XGBoost training time: {train_time:.2f}s")

    return model

def train_lightgbm(X_train, y_train, X_val, y_val, class_weight=None) -> lgb.LGBMClassifier:
    """Train LightGBM model."""
    logger.info("Training LightGBM...")
    start_time = time.time()

    # LightGBM requires numeric labels, so we encode the string labels
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_val_enc = le.transform(y_val)

    # Convert class_weight dict from string labels to integer indices if provided
    if class_weight is not None:
        class_weight = {le.transform([cls])[0]: weight for cls, weight in class_weight.items()}

    model = lgb.LGBMClassifier(
        n_estimators=100,
        random_state=config.get("seed", 42),
        n_jobs=-1,
        class_weight=class_weight,
        verbose=-1
    )
    model.fit(
        X_train, y_train_enc,
        eval_set=[(X_val, y_val_enc)],
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(10)]
    )
    # Store the label encoder for inverse transformation during evaluation
    model.label_encoder_ = le

    # Validate
    y_val_pred_enc = model.predict(X_val)
    y_val_pred = le.inverse_transform(y_val_pred_enc)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    logger.info(f"LightGBM validation macro-F1: {val_f1:.4f}")

    train_time = time.time() - start_time
    logger.info(f"LightGBM training time: {train_time:.2f}s")

    return model

def train_mlp(X_train, y_train, X_val, y_val, class_weight=None) -> MLPClassifier:
    """Train MLP model."""
    logger.info("Training MLP...")
    start_time = time.time()

    model = MLPClassifier(
        hidden_layer_sizes=(100, 50),
        random_state=config.get("seed", 42),
        max_iter=500,
        early_stopping=True,
        validation_fraction=0.1
    )
    model.fit(X_train, y_train)

    # Validate
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')
    logger.info(f"MLP validation macro-F1: {val_f1:.4f}")

    train_time = time.time() - start_time
    logger.info(f"MLP training time: {train_time:.2f}s")

    return model

def evaluate_model(model, X_test, y_test, model_name: str) -> Dict[str, Any]:
    """Evaluate model on test set."""
    logger.info(f"Evaluating {model_name} on test set...")

    # Predict
    if hasattr(model, 'label_encoder_'):
        # For models that require label encoding (like our modified XGBoost)
        y_test_pred_enc = model.predict(X_test)
        y_test_pred = model.label_encoder_.inverse_transform(y_test_pred_enc)
    else:
        y_test_pred = model.predict(X_test)

    # Calculate metrics
    accuracy = f1_score(y_test, y_test_pred, average='micro')  # Accuracy for classification
    macro_f1 = f1_score(y_test, y_test_pred, average='macro')
    weighted_f1 = f1_score(y_test, y_test_pred, average='weighted')

    # Per-class metrics
    report = classification_report(y_test, y_test_pred, output_dict=True)

    # Confusion matrix
    cm = confusion_matrix(y_test, y_test_pred)

    # Inference time
    import time
    start_time = time.time()
    _ = model.predict(X_test[:100])  # Predict on 100 samples
    inference_time_per_1000 = (time.time() - start_time) * 1000 * (1000 / 100)  # Scale to per 1000

    metrics = {
        'model': model_name,
        'accuracy': float(accuracy),
        'precision': float(report['weighted avg']['precision']),
        'recall': float(report['weighted avg']['recall']),
        'f1': float(report['weighted avg']['f1-score']),
        'macro_f1': float(macro_f1),
        'weighted_f1': float(weighted_f1),
        'inference_time_per_1000': float(inference_time_per_1000),
        'confusion_matrix': cm.tolist(),
        'classification_report': report
    }

    logger.info(f"{model_name} test results:")
    logger.info(f"  Accuracy: {accuracy:.4f}")
    logger.info(f"  Macro F1: {macro_f1:.4f}")
    logger.info(f"  Weighted F1: {weighted_f1:.4f}")

    return metrics

def train_all_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    class_weight_dict: Optional[Dict] = None
) -> Dict[str, Any]:
    """Train all models and return the best one."""
    logger.info("Starting model training for all algorithms...")

    # Dictionary to store models and their metrics
    models = {}
    metrics = {}

    # Train Logistic Regression
    lr_model = train_logistic_regression(X_train, y_train, X_val, y_val, class_weight_dict)
    models['logistic_regression'] = lr_model
    metrics['logistic_regression'] = evaluate_model(lr_model, X_test, y_test, 'Logistic Regression')

    # Train Random Forest
    rf_model = train_random_forest(X_train, y_train, X_val, y_val, class_weight_dict)
    models['random_forest'] = rf_model
    metrics['random_forest'] = evaluate_model(rf_model, X_test, y_test, 'Random Forest')

    # Train XGBoost
    xgb_model = train_xgboost(X_train, y_train, X_val, y_val, class_weight_dict)
    models['xgboost'] = xgb_model
    metrics['xgboost'] = evaluate_model(xgb_model, X_test, y_test, 'XGBoost')

    # Train LightGBM
    lgb_model = train_lightgbm(X_train, y_train, X_val, y_val, class_weight_dict)
    models['lightgbm'] = lgb_model
    metrics['lightgbm'] = evaluate_model(lgb_model, X_test, y_test, 'LightGBM')

    # Train MLP
    mlp_model = train_mlp(X_train, y_train, X_val, y_val, class_weight_dict)
    models['mlp'] = mlp_model
    metrics['mlp'] = evaluate_model(mlp_model, X_test, y_test, 'MLP')

    # Determine best model based on macro F1
    best_model_name = max(metrics, key=lambda x: metrics[x]['macro_f1'])
    best_model = models[best_model_name]

    logger.info(f"Best model: {best_model_name} with macro F1: {metrics[best_model_name]['macro_f1']:.4f}")

    # Prepare results
    results = {
        'models': models,
        'metrics': metrics,
        'best_model_name': best_model_name,
        'best_model': best_model,
        'comparison_ready': True
    }

    return results

def save_models_and_results(results: Dict[str, Any], model_dir: str = "models"):
    """Save trained models and results to disk."""
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    # Save each model
    for name, model in results['models'].items():
        model_file = model_path / f"{name}.joblib"
        joblib.dump(model, model_file)
        logger.info(f"Saved {name} model to {model_file}")

    # Save metrics
    metrics_path = model_path / "metrics.json"
    # Convert numpy types to native Python for JSON serialization
    def convert_to_native(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: convert_to_native(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        else:
            return obj

    metrics_native = convert_to_native(results['metrics'])
    with open(metrics_path, 'w') as f:
        json.dump(metrics_native, f, indent=2)
    logger.info(f"Saved metrics to {metrics_path}")

    # Save best model info
    best_model_info = {
        'best_model_name': results['best_model_name'],
        'best_model_macro_f1': results['metrics'][results['best_model_name']]['macro_f1']
    }
    best_model_path = model_path / "best_model_info.json"
    with open(best_model_path, 'w') as f:
        json.dump(best_model_info, f, indent=2)
    logger.info(f"Saved best model info to {best_model_path}")

def log_to_mlflow(results: Dict[str, Any], experiment_name: str = "CyberAgent"):
    """Log training results to MLflow."""
    try:
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=f"training_{int(time.time())}") as run:
            # Log parameters
            mlflow.log_param("seed", config.get("seed", 42))

            # Log metrics for each model
            for model_name, metrics in results['metrics'].items():
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)) and metric_name not in ['confusion_matrix', 'classification_report']:
                        mlflow.log_metric(f"{model_name}_{metric_name}", value)

            # Log best model
            mlflow.log_param("best_model", results['best_model_name'])
            mlflow.log_metric("best_model_macro_f1", results['metrics'][results['best_model_name']]['macro_f1'])

            # Log the best model artifact
            best_model = results['best_model']
            if hasattr(best_model, 'named_steps'):  # Pipeline
                mlflow.sklearn.log_model(best_model, "best_model")
            else:
                # For tree-based models, log appropriately
                if isinstance(best_model, lgb.LGBMClassifier):
                    mlflow.lightgbm.log_model(best_model, "best_model")
                elif isinstance(best_model, xgb.XGBClassifier):
                    mlflow.xgboost.log_model(best_model, "best_model")
                else:
                    mlflow.sklearn.log_model(best_model, "best_model")

            logger.info(f"Logged training run to MLflow: {run.info.run_id}")

    except Exception as e:
        logger.warning(f"Failed to log to MLflow: {e}")

def main():
    """Main training function for demonstration."""
    logger.info("Starting CyberAgent training pipeline...")

    # In a real scenario, you would load and preprocess data
    # For this example, we'll use synthetic data
    from cyberagent.data_loader import load_data
    from cyberagent.preprocess import example_preprocessing_pipeline

    # Run example preprocessing to get data
    data_dict = example_preprocessing_pipeline()

    # Extract data
    X_train = data_dict['X_train']
    X_val = data_dict['X_val']
    X_test = data_dict['X_test']
    y_train = data_dict['y_train']
    y_val = data_dict['y_val']
    y_test = data_dict['y_test']

    logger.info(f"Data shapes - Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")

    # Get class weights for imbalance handling
    imbalance_info = data_dict['imbalance_info']
    class_weight_dict = imbalance_info.get('class_weight')

    # Train all models
    results = train_all_models(
        X_train, y_train, X_val, y_val, X_test, y_test, class_weight_dict
    )

    # Save models and results
    save_models_and_results(results)

    # Log to MLflow (if configured)
    log_to_mlflow(results)

    # Print summary
    logger.info("="*50)
    logger.info("TRAINING COMPLETE")
    logger.info("="*50)
    logger.info(f"Best model: {results['best_model_name']}")
    logger.info(f"Best model macro F1: {results['metrics'][results['best_model_name']]['macro_f1']:.4f}")
    logger.info(f"Models saved to: models/")
    logger.info("="*50)

    return results

if __name__ == "__main__":
    main()