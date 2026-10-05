"""
Tests for evaluation module.
"""
import sys
import os
import json
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyberagent.evaluate import (
    calculate_metrics,
    evaluate_model,
    compare_models,
    plot_confusion_matrix,
    plot_prc,
    plot_roc,
    save_evaluation_results
)
from src.cyberagent.config import config

def test_calculate_metrics():
    """Test metrics calculation."""
    # Create simple test data
    y_true = np.array([0, 1, 1, 0, 1, 0])
    y_pred = np.array([0, 1, 0, 0, 1, 1])

    # Test without probabilities
    metrics = calculate_metrics(y_true, y_pred)

    # Check that we got the expected metrics
    assert 'accuracy' in metrics
    assert 'macro_f1' in metrics
    assert 'weighted_f1' in metrics
    assert 'macro_precision' in metrics
    assert 'macro_recall' in metrics
    assert 'confusion_matrix' in metrics
    assert 'classification_report' in metrics

    # Check some values manually
    # Accuracy: 4/6 = 0.666...
    assert abs(metrics['accuracy'] - 2/3) < 0.001

    print("calculate_metrics tests passed!")

def test_compare_models():
    """Test model comparison function."""
    # Create mock results
    results = {
        'Model A': {
            'accuracy': 0.8,
            'macro_f1': 0.75,
            'weighted_f1': 0.78,
            'macro_precision': 0.76,
            'macro_recall': 0.74
        },
        'Model B': {
            'accuracy': 0.85,
            'macro_f1': 0.82,
            'weighted_f1': 0.84,
            'macro_precision': 0.83,
            'macro_recall': 0.81
        }
    }

    df = compare_models(results)

    # Check DataFrame structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ['Model', 'Accuracy', 'Macro F1', 'Weighted F1', 'Macro Precision', 'Macro Recall']

    # Check values
    assert df.iloc[0]['Model'] == 'Model A'
    assert df.iloc[0]['Accuracy'] == 0.8
    assert df.iloc[1]['Model'] == 'Model B'
    assert df.iloc[1]['Accuracy'] == 0.85

    print("compare_models tests passed!")

def test_save_evaluation_results():
    """Test saving evaluation results."""
    import tempfile
    import shutil

    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Create mock results
        results = {
            'models': {
                'Logistic Regression': {
                    'accuracy': 0.8,
                    'macro_f1': 0.75,
                    'weighted_f1': 0.78,
                    'macro_precision': 0.76,
                    'macro_recall': 0.74
                }
            },
            'model_comparison': pd.DataFrame({
                'Model': ['Logistic Regression'],
                'Accuracy': [0.8],
                'Macro F1': [0.75],
                'Weighted F1': [0.78],
                'Macro Precision': [0.76],
                'Macro Recall': [0.74]
            })
        }

        # Test saving
        save_evaluation_results(results, str(temp_dir))

        # Check that files were created
        assert (temp_dir / "metrics.json").exists()
        assert (temp_dir / "model_comparison.csv").exists()
        assert (temp_dir / "model_comparison.md").exists()

        # Check JSON content
        with open(temp_dir / "metrics.json", 'r') as f:
            data = json.load(f)
            assert 'models' in data
            assert 'model_comparison' in data

    finally:
        # Clean up
        shutil.rmtree(temp_dir)

    print("save_evaluation_results tests passed!")

if __name__ == "__main__":
    test_calculate_metrics()
    test_compare_models()
    test_save_evaluation_results()
    print("All evaluation tests passed!")