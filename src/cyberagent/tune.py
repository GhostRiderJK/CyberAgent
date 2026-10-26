"""
Hyperparameter tuning module for CyberAgent.
Handles Optuna-based hyperparameter optimization for models.
"""
import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Callable
import time
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
from sklearn.model_selection import cross_val_score
from sklearn.metrics import f1_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
import lightgbm as lgb
import xgboost as xgb
from cyberagent.config import config
from cyberagent.logging_setup import logger
import mlflow
import mlflow.sklearn
import mlflow.lightgbm

def objective_lgbm(trial, X_train, y_train, X_val, y_val, class_weight=None):
    """Objective function for LightGBM hyperparameter tuning."""
    param = {
        'objective': 'multiclass',
        'num_class': len(np.unique(y_train)),
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'verbosity': -1,
        'random_state': config.get("seed", 42),
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 3, 15),
        'learning_rate': trial.suggest_loguniform('learning_rate', 0.01, 0.3),
        'num_leaves': trial.suggest_int('num_leaves', 10, 300),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'subsample': trial.suggest_uniform('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.6, 1.0),
        'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-8, 10.0),
        'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-8, 10.0),
    }

    if class_weight is not None:
        param['class_weight'] = class_weight

    # Prepare datasets for LightGBM
    lgb_train = lgb.Dataset(X_train, label=y_train)
    lgb_val = lgb.Dataset(X_val, label=y_val, reference=lgb_train)

    # Train model
    model = lgb.train(
        param,
        lgb_train,
        valid_sets=[lgb_val],
        verbose_eval=False,
        early_stopping_rounds=20
    )

    # Predict and calculate macro F1
    y_val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    y_val_pred_labels = np.argmax(y_val_pred, axis=1)
    # Convert numeric predictions back to original labels
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    le.fit(y_train)
    y_val_pred_labels = le.inverse_transform(y_val_pred_labels)
    val_f1 = f1_score(y_val, y_val_pred_labels, average='macro')

    return val_f1

def objective_xgb(trial, X_train, y_train, X_val, y_val, class_weight=None):
    """Objective function for XGBoost hyperparameter tuning."""
    param = {
        'objective': 'multi:softprob',
        'num_class': len(np.unique(y_train)),
        'eval_metric': 'mlogloss',
        'booster': 'gbtree',
        'random_state': config.get("seed", 42),
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 3, 15),
        'learning_rate': trial.suggest_loguniform('learning_rate', 0.01, 0.3),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'subsample': trial.suggest_uniform('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.6, 1.0),
        'gamma': trial.suggest_loguniform('gamma', 1e-8, 10.0),
        'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-8, 10.0),
        'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-8, 10.0),
    }

    # Note: XGBoost handles class_weight differently, we'll skip for now
    # In a full implementation, we would use scale_pos_weight for binary or sample_weights

    # Prepare datasets for XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval = xgb.DMatrix(X_val, label=y_val)

    # Train model
    model = xgb.train(
        param,
        dtrain,
        num_boost_round=param['n_estimators'],
        evals=[(dval, 'validation')],
        early_stopping_rounds=20,
        verbose_eval=False
    )

    # Predict and calculate macro F1
    y_val_pred = model.predict(dval)
    y_val_pred_labels = np.argmax(y_val_pred, axis=1)
    val_f1 = f1_score(y_val, y_val_pred_labels, average='macro')

    return val_f1

def objective_rf(trial, X_train, y_train, X_val, y_val, class_weight=None):
    """Objective function for Random Forest hyperparameter tuning."""
    param = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 300),
        'max_depth': trial.suggest_int('max_depth', 3, 15),
        'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
        'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 20),
        'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
        'random_state': config.get("seed", 42),
        'n_jobs': -1,
    }

    if class_weight is not None:
        param['class_weight'] = class_weight

    model = RandomForestClassifier(**param)
    model.fit(X_train, y_train)

    # Predict and calculate macro F1
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')

    return val_f1

def objective_lr(trial, X_train, y_train, X_val, y_val, class_weight=None):
    """Objective function for Logistic Regression hyperparameter tuning."""
    param = {
        'C': trial.suggest_loguniform('C', 1e-4, 1e2),
        'penalty': trial.suggest_categorical('penalty', ['l1', 'l2', 'elasticnet']),
        'solver': trial.suggest_categorical('solver', ['lbfgs', 'liblinear', 'saga']),
        'random_state': config.get("seed", 42),
        'max_iter': 1000,
        'n_jobs': -1,
    }

    # Handle solver-penalty compatibility
    if param['penalty'] == 'l1' and param['solver'] not in ['liblinear', 'saga']:
        raise optuna.exceptions.TrialPruned()
    if param['penalty'] == 'l2' and param['solver'] == 'liblinear':
        pass  # liblinear supports l2
    if param['penalty'] == 'elasticnet' and param['solver'] != 'saga':
        raise optuna.exceptions.TrialPruned()
    if param['penalty'] == 'elasticnet':
        param['l1_ratio'] = trial.suggest_uniform('l1_ratio', 0, 1)

    if class_weight is not None:
        param['class_weight'] = class_weight

    model = LogisticRegression(**param)
    model.fit(X_train, y_train)

    # Predict and calculate macro F1
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')

    return val_f1

def objective_mlp(trial, X_train, y_train, X_val, y_val, class_weight=None):
    """Objective function for MLP hyperparameter tuning."""
    param = {
        'hidden_layer_sizes': trial.suggest_categorical('hidden_layer_sizes', [
            (50,), (100,), (50, 25), (100, 50), (100, 50, 25)
        ]),
        'activation': trial.suggest_categorical('activation', ['relu', 'tanh', 'logistic']),
        'alpha': trial.suggest_loguniform('alpha', 1e-5, 1e+1),
        'learning_rate': trial.suggest_categorical('learning_rate', ['constant', 'invscaling', 'adaptive']),
        'learning_rate_init': trial.suggest_loguniform('learning_rate_init', 1e-4, 1e-1),
        'random_state': config.get("seed", 42),
        'max_iter': 500,
        'early_stopping': True,
    }

    if class_weight is not None:
        # MLP doesn't directly support class_weight, we'll use sample_weight
        # For simplicity, we'll skip this in the objective
        pass

    model = MLPClassifier(**param)
    model.fit(X_train, y_train)

    # Predict and calculate macro F1
    y_val_pred = model.predict(X_val)
    val_f1 = f1_score(y_val, y_val_pred, average='macro')

    return val_f1

def run_optuna_study(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    class_weight: Optional[Dict] = None,
    n_trials: Optional[int] = None,
    timeout: Optional[int] = None
) -> Tuple[Any, Dict[str, Any]]:
    """Run Optuna study for a specific model."""
    if n_trials is None:
        n_trials = config.get("tuning.n_trials", 50)
    if timeout is None:
        timeout = config.get("tuning.timeout", 3600)

    logger.info(f"Starting Optuna study for {model_name} with {n_trials} trials...")

    # Define objective function based on model
    objective_funcs = {
        'lightgbm': lambda trial: objective_lgbm(trial, X_train, y_train, X_val, y_val, class_weight),
        'xgboost': lambda trial: objective_xgb(trial, X_train, y_train, X_val, y_val, class_weight),
        'random_forest': lambda trial: objective_rf(trial, X_train, y_train, X_val, y_val, class_weight),
        'logistic_regression': lambda trial: objective_lr(trial, X_train, y_train, X_val, y_val, class_weight),
        'mlp': lambda trial: objective_mlp(trial, X_train, y_train, X_val, y_val, class_weight),
    }

    if model_name not in objective_funcs:
        raise ValueError(f"Unsupported model for tuning: {model_name}")

    objective = objective_funcs[model_name]

    # Create study
    sampler = TPESampler(seed=config.get("seed", 42))
    pruner = MedianPruner(n_startup_trials=5, n_warmup_steps=0)

    study = optuna.create_study(
        direction='maximize',
        sampler=sampler,
        pruner=pruner,
        study_name=f"{model_name}_tuning"
    )

    # Optimize
    study.optimize(objective, n_trials=n_trials, timeout=timeout)

    logger.info(f"Optuna study for {model_name} completed.")
    logger.info(f"Best value (macro F1): {study.best_value:.4f}")
    logger.info(f"Best params: {study.best_params}")

    # Return best trial and study
    return study.best_trial, study

def tune_all_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    class_weight_dict: Optional[Dict] = None,
    n_trials_per_model: Optional[int] = None,
    timeout_per_model: Optional[int] = None
) -> Dict[str, Any]:
    """Run hyperparameter tuning for all models."""
    logger.info("Starting hyperparameter tuning for all models...")

    # Models to tune
    models_to_tune = ['lightgbm', 'xgboost', 'random_forest', 'logistic_regression', 'mlp']

    # Override config if provided
    if n_trials_per_model is None:
        n_trials_per_model = config.get("tuning.n_trials", 50)
    if timeout_per_model is None:
        timeout_per_model = config.get("tuning.timeout", 3600)

    results = {}
    best_overall_value = -1
    best_overall_model = None
    best_overall_params = None

    for model_name in models_to_tune:
        logger.info(f"Tuning {model_name}...")

        try:
            best_trial, study = run_optuna_study(
                model_name, X_train, y_train, X_val, y_val,
                class_weight_dict, n_trials_per_model, timeout_per_model
            )

            results[model_name] = {
                'best_trial': best_trial,
                'study': study,
                'best_value': best_trial.value,
                'best_params': best_trial.params
            }

            # Track best overall model
            if best_trial.value > best_overall_value:
                best_overall_value = best_trial.value
                best_overall_model = model_name
                best_overall_params = best_trial.params

        except Exception as e:
            logger.error(f"Failed to tune {model_name}: {e}")
            results[model_name] = {
                'error': str(e)
            }

    logger.info(f"Hyperparameter tuning complete. Best model: {best_overall_model} with F1: {best_overall_value:.4f}")

    # Prepare final results
    tuning_results = {
        'results': results,
        'best_model': best_overall_model,
        'best_value': best_overall_value,
        'best_params': best_overall_params,
        'n_trials_per_model': n_trials_per_model,
        'timeout_per_model': timeout_per_model
    }

    return tuning_results

def apply_best_params(
    model_name: str,
    best_params: Dict[str, Any],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    class_weight: Optional[Dict] = None
) -> Any:
    """Create and train a model with the best hyperparameters."""
    logger.info(f"Training final {model_name} model with best parameters...")

    start_time = time.time()

    if model_name == 'lightgbm':
        param = {
            'objective': 'multiclass',
            'num_class': len(np.unique(y_train)),
            'metric': 'multi_logloss',
            'boosting_type': 'gbdt',
            'verbosity': -1,
            'random_state': config.get("seed", 42),
        }
        param.update(best_params)
        if class_weight is not None:
            param['class_weight'] = class_weight

        lgb_train = lgb.Dataset(X_train, label=y_train)
        model = lgb.train(
            param,
            lgb_train,
            num_boost_round=best_params.get('n_estimators', 100),
            verbose_eval=False
        )

    elif model_name == 'xgboost':
        param = {
            'objective': 'multi:softprob',
            'num_class': len(np.unique(y_train)),
            'eval_metric': 'mlogloss',
            'booster': 'gbtree',
            'random_state': config.get("seed", 42),
        }
        param.update(best_params)

        dtrain = xgb.DMatrix(X_train, label=y_train)
        model = xgb.train(
            param,
            dtrain,
            num_boost_round=best_params.get('n_estimators', 100),
            verbose_eval=False
        )

    elif model_name == 'random_forest':
        param = {
            'random_state': config.get("seed", 42),
            'n_jobs': -1,
        }
        param.update(best_params)
        if class_weight is not None:
            param['class_weight'] = class_weight

        model = RandomForestClassifier(**param)
        model.fit(X_train, y_train)

    elif model_name == 'logistic_regression':
        param = {
            'random_state': config.get("seed", 42),
            'max_iter': 1000,
            'n_jobs': -1,
        }
        param.update(best_params)
        if class_weight is not None:
            param['class_weight'] = class_weight
        # Handle l1_ratio for elasticnet
        if param.get('penalty') == 'elasticnet' and 'l1_ratio' not in param:
            param['l1_ratio'] = 0.5

        model = LogisticRegression(**param)
        model.fit(X_train, y_train)

    elif model_name == 'mlp':
        param = {
            'random_state': config.get("seed", 42),
            'max_iter': 500,
            'early_stopping': True,
        }
        param.update(best_params)

        model = MLPClassifier(**param)
        model.fit(X_train, y_train)

    else:
        raise ValueError(f"Unsupported model for final training: {model_name}")

    train_time = time.time() - start_time
    logger.info(f"Final {model_name} model training time: {train_time:.2f}s")

    return model

def main():
    """Main tuning function for demonstration."""
    logger.info("Starting CyberAgent hyperparameter tuning...")

    # In a real scenario, you would load and preprocess data
    # For this example, we'll use synthetic data
    from cyberagent.data_loader import load_data
    from cyberagent.preprocess import example_preprocessing_pipeline

    # Run example preprocessing to get data
    data_dict = example_preprocessing_pipeline()

    # Extract data
    X_train = data_dict['X_train']
    X_val = data_dict['X_val']
    y_train = data_dict['y_train']
    y_val = data_dict['y_val']

    logger.info(f"Data shapes - Train: {X_train.shape}, Val: {X_val.shape}")

    # Get class weights for imbalance handling
    imbalance_info = data_dict['imbalance_info']
    class_weight_dict = imbalance_info.get('class_weight')

    # Run hyperparameter tuning (with reduced trials for demo)
    tuning_results = tune_all_models(
        X_train, y_train, X_val, y_val,
        class_weight_dict,
        n_trials_per_model=5,  # Reduced for demo
        timeout_per_model=300   # 5 minutes per model
    )

    # Save tuning results
    results_dir = Path("results/tables")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Convert to JSON-serializable format
    def convert_to_native(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: convert_to_native(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        elif hasattr(obj, 'params'):  # Optuna trial
            return {
                'value': obj.value,
                'params': obj.params,
                'number': obj.number
            }
        else:
            return str(obj)  # Fallback for unknown types

    # Save summary (without full study objects which are too large)
    summary = {
        'best_model': tuning_results['best_model'],
        'best_value': tuning_results['best_value'],
        'best_params': tuning_results['best_params'],
        'model_results': {}
    }

    for model_name, result in tuning_results['results'].items():
        if 'error' not in result:
            summary['model_results'][model_name] = {
                'best_value': result['best_value'],
                'best_params': result['best_params']
            }
        else:
            summary['model_results'][model_name] = {
                'error': result['error']
            }

    results_path = results_dir / "tuning_results.json"
    with open(results_path, 'w') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Saved tuning results to {results_path}")

    # Train final models with best parameters
    logger.info("Training final models with best parameters...")
    final_models = {}
    for model_name in ['lightgbm', 'xgboost', 'random_forest', 'logistic_regression', 'mlp']:
        if model_name in tuning_results['results'] and 'error' not in tuning_results['results'][model_name]:
            best_params = tuning_results['results'][model_name]['best_params']
            model = apply_best_params(model_name, best_params, X_train, y_train, class_weight_dict)
            final_models[model_name] = model
            logger.info(f"Trained final {model_name} model")

    # Print summary
    logger.info("="*50)
    logger.info("TUNING COMPLETE")
    logger.info("="*50)
    logger.info(f"Best model: {tuning_results['best_model']}")
    logger.info(f"Best macro F1: {tuning_results['best_value']:.4f}")
    logger.info(f"Best params: {tuning_results['best_params']}")
    logger.info(f"Results saved to: {results_path}")
    logger.info("="*50)

    return tuning_results, final_models

if __name__ == "__main__":
    main()