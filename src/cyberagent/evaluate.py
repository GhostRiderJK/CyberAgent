"""
Evaluation module for CyberAgent.
Handles model evaluation, metrics calculation, and result reporting.
"""
import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score,
    confusion_matrix, classification_report,
    precision_recall_curve, roc_curve, auc
)
from src.cyberagent.config import config
from src.cyberagent.logging_setup import logger

def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_pred_proba: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """
    Calculate evaluation metrics.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_pred_proba: Predicted probabilities (optional)

    Returns:
        Dictionary of metrics
    """
    # Basic metrics
    accuracy = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average='macro')
    weighted_f1 = f1_score(y_true, y_pred, average='weighted')
    macro_precision = precision_score(y_true, y_pred, average='macro')
    macro_recall = recall_score(y_true, y_pred, average='macro')

    # Per-class metrics
    report = classification_report(y_true, y_pred, output_dict=True)

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)

    metrics = {
        'accuracy': float(accuracy),
        'macro_f1': float(macro_f1),
        'weighted_f1': float(weighted_f1),
        'macro_precision': float(macro_precision),
        'macro_recall': float(macro_recall),
        'confusion_matrix': cm.tolist(),
        'classification_report': report
    }

    # If probabilities are provided, calculate PRC and ROC
    if y_pred_proba is not None:
        # Binarize labels for multiclass PRC/ROC
        from sklearn.preprocessing import LabelBinarizer
        lb = LabelBinarizer()
        y_true_bin = lb.fit_transform(y_true)
        # If binary classification, LB returns shape (n_samples, 1)
        if y_true_bin.shape[1] == 1:
            y_true_bin = np.hstack([1 - y_true_bin, y_true_bin])

        # For each class, calculate PRC and ROC
        prc_data = {}
        roc_data = {}
        for i, class_label in enumerate(lb.classes_):
            if i < y_pred_proba.shape[1]:  # Check if we have probabilities for this class
                precision, recall, _ = precision_recall_curve(y_true_bin[:, i], y_pred_proba[:, i])
                prc_auc = auc(recall, precision)
                fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_pred_proba[:, i])
                roc_auc = auc(fpr, tpr)

                prc_data[str(class_label)] = {
                    'precision': precision.tolist(),
                    'recall': recall.tolist(),
                    'auc': float(prc_auc)
                }
                roc_data[str(class_label)] = {
                    'fpr': fpr.tolist(),
                    'tpr': tpr.tolist(),
                    'auc': float(roc_auc)
                }

        metrics['prc'] = prc_data
        metrics['roc'] = roc_data

    return metrics

def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series, model_name: str) -> Dict[str, Any]:
    """
    Evaluate a single model on test set.

    Args:
        model: Trained model
        X_test: Test features
        y_test: Test labels
        model_name: Name of the model

    Returns:
        Dictionary of evaluation results
    """
    logger.info(f"Evaluating {model_name}...")

    # Predict
    y_test_pred = model.predict(X_test)

    # Get probabilities if available
    y_test_proba = None
    if hasattr(model, "predict_proba"):
        y_test_proba = model.predict_proba(X_test)
    elif hasattr(model, "predict_log_proba"):
        y_test_proba = np.exp(model.predict_log_proba(X_test))
    # For tree-based models like LightGBM and XGBoost, we can use predict_proba
    elif str(type(model)).find('LGBM') != -1 or str(type(model)).find('XGB') != -1:
        if hasattr(model, "predict_proba"):
            y_test_proba = model.predict_proba(X_test)

    # Calculate metrics
    metrics = calculate_metrics(y_test.values, y_test_pred, y_test_proba)
    metrics['model'] = model_name

    logger.info(f"{model_name} - Accuracy: {metrics['accuracy']:.4f}, Macro F1: {metrics['macro_f1']:.4f}")

    return metrics

def compare_models(results: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """
    Compare multiple models and return a DataFrame for easy viewing.

    Args:
        results: Dictionary mapping model names to their evaluation results

    Returns:
        DataFrame with model comparison
    """
    rows = []
    for model_name, metrics in results.items():
        row = {
            'Model': model_name,
            'Accuracy': metrics.get('accuracy', 0),
            'Macro F1': metrics.get('macro_f1', 0),
            'Weighted F1': metrics.get('weighted_f1', 0),
            'Macro Precision': metrics.get('macro_precision', 0),
            'Macro Recall': metrics.get('macro_recall', 0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df

def plot_confusion_matrix(cm: np.ndarray, class_names: List[str], title: str = "Confusion Matrix",
                         figsize: Tuple[int, int] = (8, 6), save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot confusion matrix.

    Args:
        cm: Confusion matrix array
        class_names: List of class names
        title: Plot title
        figsize: Figure size
        save_path: Path to save the figure (optional)

    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=class_names, yticklabels=class_names, ax=ax)
    ax.set_title(title)
    ax.set_ylabel('True Label')
    ax.set_xlabel('Predicted Label')

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
        logger.info(f"Saved confusion matrix to {save_path}")

    return fig

def plot_prc(prc_data: Dict[str, Any], title: str = "Precision-Recall Curves",
             figsize: Tuple[int, int] = (8, 6), save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot Precision-Recall curves.

    Args:
        prc_data: Dictionary with PRC data for each class
        title: Plot title
        figsize: Figure size
        save_path: Path to save the figure (optional)

    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    for class_name, data in prc_data.items():
        ax.plot(data['recall'], data['precision'],
                label=f'{class_name} (AUC = {data["auc"]:.3f})')
    ax.set_xlabel('Recall')
    ax.set_ylabel('Precision')
    ax.set_title(title)
    ax.legend(loc='best')
    ax.grid(True)

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
        logger.info(f"Saved PRC plot to {save_path}")

    return fig

def plot_roc(roc_data: Dict[str, Any], title: str = "ROC Curves",
             figsize: Tuple[int, int] = (8, 6), save_path: Optional[str] = None) -> plt.Figure:
    """
    Plot ROC curves.

    Args:
        roc_data: Dictionary with ROC data for each class
        title: Plot title
        figsize: Tuple[int, int] = (8, 6), save_path: Optional[str] = None) -> plt.Figure:
    """
    fig, ax = plt.subplots(figsize=figsize)
    for class_name, data in roc_data.items():
        ax.plot(data['fpr'], data['tpr'],
                label=f'{class_name} (AUC = {data["auc"]:.3f})')
    ax.plot([0, 1], [0, 1], 'k--', label='Random')
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title(title)
    ax.legend(loc='best')
    ax.grid(True)

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
        logger.info(f"Saved ROC plot to {save_path}")

    return fig

def save_evaluation_results(results: Dict[str, Any], output_dir: str = "results") -> None:
    """
    Save evaluation results to disk.

    Args:
        results: Dictionary of evaluation results
        output_dir: Directory to save results
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save metrics as JSON
    metrics_path = output_path / "metrics.json"
    # Convert numpy types to native Python
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
            return str(obj)  # Fallback for unknown types

    metrics_native = convert_to_native(results)
    with open(metrics_path, 'w') as f:
        json.dump(metrics_native, f, indent=2)
    logger.info(f"Saved evaluation metrics to {metrics_path}")

    # Save comparison table as CSV and markdown
    if 'model_comparison' in results:
        comp_df = results['model_comparison']
        comp_path_csv = output_path / "model_comparison.csv"
        comp_df.to_csv(comp_path_csv, index=False)
        logger.info(f"Saved model comparison CSV to {comp_path_csv}")

        comp_path_md = output_path / "model_comparison.md"
        with open(comp_path_md, 'w') as f:
            f.write(comp_df.to_markdown(index=False))
        logger.info(f"Saved model comparison markdown to {comp_path_md}")

if __name__ == "__main__":
    # This is to allow running the module directly for testing
    pass