"""Tests for the evaluation artifact builder (scripts/build_evaluation_json.py).

The golden rule these enforce: every number the frontend shows must be recomputable
from the confusion matrix, and anything that cannot be recomputed must fail loudly
instead of being quietly displayed.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_evaluation_json.py"

_spec = importlib.util.spec_from_file_location("build_evaluation_json", SCRIPT)
bez = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bez)


def test_matrix_metrics_rederives_headline_numbers():
    labels = ["A", "B"]
    matrix = [[40, 2], [3, 15]]
    d = bez._matrix_metrics(matrix, labels)
    assert d["total"] == 60
    assert d["correct"] == 55
    assert d["accuracy"] == pytest.approx(55 / 60)
    assert d["per_class"]["A"]["precision"] == pytest.approx(40 / 43)
    assert d["per_class"]["A"]["recall"] == pytest.approx(40 / 42)
    assert d["per_class"]["B"]["support"] == 18


def test_self_check_accepts_a_consistent_artifact():
    labels = ["A", "B"]
    matrix = [[40, 2], [3, 15]]
    derived = bez._matrix_metrics(matrix, labels)
    metrics = {"precision": derived["precision_weighted"],
               "recall": derived["recall_weighted"], "f1": derived["f1_weighted"]}
    bez._self_check("m", metrics, derived, derived["accuracy"], derived["f1_macro"], 60)


def test_self_check_rejects_a_matrix_that_disagrees_with_accuracy():
    """The exact bug this task fixes: headline 99.89% next to a ~92% matrix."""
    labels = ["A", "B"]
    matrix = [[40, 2], [3, 15]]
    derived = bez._matrix_metrics(matrix, labels)
    with pytest.raises(bez.ArtifactError, match="Self-check FAILED"):
        bez._self_check("m", {}, derived, 0.9989, derived["f1_macro"], 60)


def test_self_check_rejects_wrong_sample_count():
    labels = ["A", "B"]
    matrix = [[40, 2], [3, 15]]
    derived = bez._matrix_metrics(matrix, labels)
    with pytest.raises(bez.ArtifactError, match="n_samples"):
        bez._self_check("m", {}, derived, derived["accuracy"], derived["f1_macro"], 999)


def test_labels_must_match_matrix_shape():
    report = {"A": {}, "B": {}, "accuracy": {"accuracy": 1.0}}
    with pytest.raises(bez.ArtifactError, match="does not match"):
        bez._labels_from_report(report, [[1, 0]])


def test_pr_curve_is_reversed_bounded_and_capped():
    n = 5000
    summary = {"test_set": {"lightgbm": {"prc": {"Bot": {
        "precision": [1.0 - i / (n - 1) for i in range(n)],
        "recall": [1.0 - i / (n - 1) for i in range(n)],
        "auc": 0.5123,
    }}}}}
    curves = bez._pr_curve_for_model(summary, "lightgbm")
    pts = curves["Bot"]["points"]
    assert len(pts) <= bez.MAX_PR_POINTS
    assert pts[0] == {"recall": 0.0, "precision": 0.0}
    assert pts[-1] == {"recall": 1.0, "precision": 1.0}
    assert curves["Bot"]["average_precision"] == pytest.approx(0.5123)
    assert curves["Bot"]["n_thresholds"] == n
    for p in pts:
        assert 0.0 <= p["recall"] <= 1.0 and 0.0 <= p["precision"] <= 1.0
    assert all(b["recall"] >= a["recall"] for a, b in zip(pts, pts[1:]))


def test_short_curve_keeps_every_point():
    summary = {"test_set": {"lightgbm": {"prc": {"Bot": {
        "precision": [0.5, 0.75, 1.0], "recall": [1.0, 0.5, 0.0], "auc": 0.8}}}}}
    pts = bez._pr_curve_for_model(summary, "lightgbm")["Bot"]["points"]
    assert [p["recall"] for p in pts] == [0.0, 0.5, 1.0]
    assert [p["precision"] for p in pts] == [1.0, 0.75, 0.5]


def test_pr_curve_rejects_out_of_range_values():
    summary = {"test_set": {"lightgbm": {"prc": {"Bot": {
        "precision": [1.2, 0.5], "recall": [0.0, 1.0], "auc": 0.9}}}}}
    with pytest.raises(bez.ArtifactError, match=r"leaves \[0,1\]"):
        bez._pr_curve_for_model(summary, "lightgbm")


def test_pr_curve_requires_the_selected_model():
    with pytest.raises(bez.ArtifactError, match="no test_set entry"):
        bez._pr_curve_for_model({"test_set": {}}, "lightgbm")


def test_missing_artifact_names_the_regeneration_command():
    with pytest.raises(bez.ArtifactError, match="make train"):
        bez._load_json(REPO_ROOT / "models" / "does-not-exist.json", "models/metrics.json")


EVAL_JSON = REPO_ROOT / "artifacts" / "eval" / "evaluation.json"


@pytest.mark.skipif(not EVAL_JSON.exists(), reason="run scripts/build_evaluation_json.py first")
def test_committed_artifact_is_self_consistent():
    doc = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    matrix = doc["confusion_matrix"]["matrix"]
    labels = doc["labels"]
    assert len(matrix) == len(labels)
    assert all(len(row) == len(labels) for row in matrix)

    derived = bez._matrix_metrics(matrix, labels)
    assert derived["total"] == doc["dataset"]["n_samples"]
    assert derived["accuracy"] == pytest.approx(
        doc["models"][doc["best_model"]]["accuracy"], abs=1e-6)
    assert doc["confusion_matrix"]["accuracy"] == pytest.approx(derived["accuracy"], abs=1e-9)
    assert doc["confusion_matrix"]["support"] == [
        int(derived["per_class"][l]["support"]) for l in labels]

    best_f1 = max(m["f1_macro"] for m in doc["models"].values())
    assert doc["models"][doc["best_model"]]["f1_macro"] == pytest.approx(best_f1)

    for cls, curve in doc["pr_curves"]["curves"].items():
        assert len(curve["points"]) <= bez.MAX_PR_POINTS
        assert 0.0 <= curve["average_precision"] <= 1.0
        for p in curve["points"]:
            assert 0.0 <= p["precision"] <= 1.0, f"{cls} precision out of [0,1]"
            assert 0.0 <= p["recall"] <= 1.0, f"{cls} recall out of [0,1]"
