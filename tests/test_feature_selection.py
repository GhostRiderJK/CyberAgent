"""Tests for FeatureSelector. Uses only tiny synthetic data and tmp_path."""
import numpy as np
import pandas as pd
import pytest

from cyberagent.feature_selection import FeatureSelector


def make_frame(n=400, seed=0):
    rng = np.random.RandomState(seed)
    y = rng.randint(0, 2, n)
    informative = y + rng.normal(0, 0.3, n)
    noise1 = rng.normal(size=n)
    noise2 = rng.normal(size=n)
    X = pd.DataFrame({
        "informative": informative,
        "informative_copy": informative * 3.0 + 1.0,   # perfectly correlated duplicate
        "constant": 7.0,
        "noise1": noise1,
        "noise2": noise2,
    })
    return X, pd.Series(y, name="Label")


def test_constant_and_correlated_dropped_with_partner():
    X, y = make_frame()
    sel = FeatureSelector(corr_threshold=0.95, top_k=None).fit(X, y)
    assert "constant" in sel.dropped_constant_
    assert sel.dropped_corr_ == {"informative_copy": "informative"}
    assert sel.selected_ == ["informative", "noise1", "noise2"]


def test_top_k_uses_y_and_keeps_informative_feature():
    X, y = make_frame()
    sel = FeatureSelector(corr_threshold=0.95, top_k=1, seed=1).fit(X, y)
    assert sel.selected_ == ["informative"]
    assert set(sel.dropped_selection_) == {"noise1", "noise2"}
    assert sel.mi_scores_["informative"] > sel.mi_scores_["noise1"]


def test_transform_uses_train_selection_only():
    X, y = make_frame()
    sel = FeatureSelector(top_k=None).fit(X.iloc[:300], y.iloc[:300])
    other = X.iloc[300:].copy()
    other["informative_copy"] = 0.0  # would change correlations if refit on this
    out = sel.transform(other)
    assert list(out.columns) == sel.selected_
    assert len(out) == 100


def test_transform_before_fit_raises():
    X, _ = make_frame()
    with pytest.raises(RuntimeError):
        FeatureSelector().transform(X)


def test_missing_column_at_transform_raises():
    X, y = make_frame()
    sel = FeatureSelector(top_k=None).fit(X, y)
    with pytest.raises(KeyError):
        sel.transform(X.drop(columns=["noise1"]))


def test_nan_values_do_not_break_fit_and_input_is_not_modified():
    X, y = make_frame()
    X.loc[::10, "noise1"] = np.nan
    before = X.copy()
    FeatureSelector(top_k=2).fit(X, y)
    pd.testing.assert_frame_equal(X, before)


def test_deterministic_for_same_seed():
    X, y = make_frame()
    a = FeatureSelector(top_k=2, seed=3).fit(X, y).selected_
    b = FeatureSelector(top_k=2, seed=3).fit(X, y).selected_
    assert a == b


def test_report_and_csv(tmp_path):
    X, y = make_frame()
    sel = FeatureSelector(top_k=1).fit(X, y)
    rep = sel.report()
    assert set(rep["status"]) == {"kept", "dropped"}
    assert rep.loc[rep.feature == "informative_copy", "kept_partner"].item() == "informative"
    path = sel.save_report(tmp_path / "sub" / "selected_features.csv")
    assert path.exists()
    assert len(pd.read_csv(path)) == X.shape[1]


def test_length_mismatch_raises():
    X, y = make_frame()
    with pytest.raises(ValueError):
        FeatureSelector().fit(X, y.iloc[:-1])
