"""Tests for the rewritten preprocess module. Synthetic data only; nothing is written to disk."""
import numpy as np
import pandas as pd
import pytest

from src.cyberagent import preprocess as pre
from src.cyberagent.preprocess import (
    EXPECTED_SUPERVISED_LABELS, apply_label_grouping, clean_data, normalize_label,
    preprocess_train_fit, preprocess_transform, split_data,
)


# ----------------------------------------------------------------------------- labels
@pytest.mark.parametrize("raw", [
    "Web Attack \x96 XSS", "Web Attack \ufffd XSS", "Web Attack - XSS", "Web Attack  XSS",
])
def test_normalize_label_variants_and_idempotent(raw):
    once = normalize_label(raw)
    assert normalize_label(once) == once
    assert once.startswith("Web Attack")
    assert "\x96" not in once and "\ufffd" not in once


def test_web_attack_variants_group_to_single_label():
    feats = pd.DataFrame({
        "flow_id": range(5), "f": range(5),
        "Label": ["Web Attack \x96 Brute Force", "Web Attack \x96 XSS", "Web Attack  Sql Injection",
                  "BENIGN", "Web Attack"],
    })
    meta = pd.DataFrame({"flow_id": range(5)})
    out, _, _ = apply_label_grouping(feats, meta)
    assert set(out["Label"]) == {"Web Attack", "BENIGN"}


def test_apply_label_grouping_does_not_mutate_input():
    feats = pd.DataFrame({"flow_id": [0, 1], "f": [1, 2], "Label": ["Web Attack \x96 XSS", "BENIGN"]})
    before = feats.copy()
    apply_label_grouping(feats, pd.DataFrame({"flow_id": [0, 1]}))
    pd.testing.assert_frame_equal(feats, before)


# ------------------------------------------------------------------------------ clean
def _frame(n=300, seed=0):
    rng = np.random.RandomState(seed)
    df = pd.DataFrame(rng.normal(size=(n, 4)), columns=list("abcd"))
    df["Label"] = "BENIGN"
    df["flow_id"] = np.arange(n)
    return df


def _append_copies(df, rows, copies, labels=None):
    extra = pd.concat([df.iloc[rows]] * copies, ignore_index=True)
    if labels is not None:
        extra["Label"] = labels
    extra["flow_id"] = np.arange(df["flow_id"].max() + 1, df["flow_id"].max() + 1 + len(extra))
    return pd.concat([df, extra], ignore_index=True)


def test_clean_data_row_accounting_and_nan_groups_keep_one_row():
    df = _frame()
    df.loc[:2, "a"] = np.nan                       # three rows that contain NaN
    df = _append_copies(df, [0, 1, 2], copies=3)    # each now has 3 extra copies (NaN-containing groups)
    meta = pd.DataFrame({"flow_id": df["flow_id"]})
    stats = {}
    out, meta_out = clean_data(df, meta, handle_impossible_negatives=False,
                               drop_constant_columns=False, stats=stats)
    assert stats["rows_in"] - stats["rows_removed_total"] == stats["rows_out"] == len(out)
    assert len(out) == len(df) - 9                  # 3 groups x 3 extra copies removed, 3 kept
    assert out["a"].isna().sum() == 3               # NaN rows survive (one per group)
    assert set(meta_out["flow_id"]) == set(out["flow_id"])


def test_cross_label_duplicates_dropped_when_rare():
    df = _frame(n=1000)
    df = _append_copies(df, [5], copies=1, labels=["PortScan"])   # same features, different label
    meta = pd.DataFrame({"flow_id": df["flow_id"]})
    stats = {}
    out, _ = clean_data(df, meta, handle_impossible_negatives=False, drop_constant_columns=False, stats=stats)
    assert stats["cross_label_rows"] == 2 and stats["dropped_cross_label"] == 2
    assert len(out) == len(df) - 2
    assert len(stats) > 0 and stats["cross_label_pct"] < 0.5


def test_cross_label_duplicates_untouched_when_common():
    df = _frame(n=10)
    df = _append_copies(df, [0, 1], copies=1, labels=["PortScan", "PortScan"])  # 4 cross rows of 12 = 33%
    meta = pd.DataFrame({"flow_id": df["flow_id"]})
    out, _ = clean_data(df, meta, handle_impossible_negatives=False, drop_constant_columns=False)
    assert len(out) == len(df)


def test_vectorised_dedupe_matches_naive_reference():
    """Compare against a plain-Python reference on a frame with NaNs, copies and cross-label pairs."""
    rng = np.random.RandomState(1)
    n = 3000
    df = pd.DataFrame(rng.normal(size=(n, 3)), columns=list("abc"))
    df.loc[rng.rand(n) < 0.1, "a"] = np.nan                       # NaN in ~10% of rows
    df["Label"] = rng.choice(["X", "Y"], size=n, p=[0.9, 0.1])
    df["flow_id"] = np.arange(n)
    # same-label duplicate copies of 200 random rows (1-3 extra copies each)
    extra = []
    for i in rng.choice(n, 200, replace=False):
        for _ in range(rng.randint(1, 4)):
            extra.append(df.iloc[i].copy())
    # two cross-label pairs (identical features, different label) -> 4 rows, well under 0.5%
    for i in (10, 20):
        row = df.iloc[i].copy()
        row["Label"] = "Y" if row["Label"] == "X" else "X"
        extra.append(row)
    df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
    df["flow_id"] = np.arange(len(df))

    stats = {}
    out, _ = clean_data(df, pd.DataFrame({"flow_id": df["flow_id"]}),
                        handle_impossible_negatives=False, drop_constant_columns=False, stats=stats)
    assert stats["cross_label_pct"] < 0.5

    groups = {}
    for fid, a, b, c, lab in zip(df["flow_id"], df["a"], df["b"], df["c"], df["Label"]):
        key = ("nan" if np.isnan(a) else a, b, c)
        groups.setdefault(key, []).append((fid, lab))
    expected_ids = set()
    for members in groups.values():
        labels = {lab for _, lab in members}
        if len(members) == 1:
            expected_ids.add(members[0][0])
        elif len(labels) == 1:
            expected_ids.add(members[0][0])          # keep the first occurrence
        # cross-label duplicate group -> drop every row
    assert set(out["flow_id"]) == expected_ids
    assert len(out) == len(expected_ids)


def test_negative_values_become_nan_and_are_counted():
    df = _frame()
    df["Flow Duration"] = 1.0
    df.loc[0:2, "Flow Duration"] = -5.0
    stats = {}
    out, _ = clean_data(df, pd.DataFrame({"flow_id": df["flow_id"]}), stats=stats,
                        drop_constant_columns=False)
    assert stats["negative_values_set_to_nan"] == {"Flow Duration": 3}
    assert out["Flow Duration"].isna().sum() == 3


# ------------------------------------------------------------------------------ split
def _split_inputs(n_per_class=40, seed=0):
    rng = np.random.RandomState(seed)
    labels = np.repeat(["A", "B", "C"], n_per_class)
    n = len(labels)
    feats = pd.DataFrame({"x": rng.normal(size=n), "y": rng.normal(size=n)})
    feats["flow_id"] = rng.permutation(np.arange(1000, 1000 + n))   # not equal to row position
    feats["Label"] = labels
    meta = pd.DataFrame({
        "flow_id": feats["flow_id"].to_numpy(),
        "Source IP": [f"10.0.0.{i % 250}" for i in range(n)],
        "Timestamp": pd.date_range("2017-07-03 09:00", periods=n, freq="min"),
    })
    meta = meta.sample(frac=1.0, random_state=3).reset_index(drop=True)   # meta in a DIFFERENT order
    return feats, meta


def test_split_aligns_metadata_by_flow_id_not_by_position():
    feats, meta = _split_inputs()
    X_tr, X_va, X_te, y_tr, y_va, y_te, m_tr, m_va, m_te = split_data(
        feats, meta, train_ratio=0.5, val_ratio=0.25, test_ratio=0.25, seed=7)
    truth = meta.set_index("flow_id")["Source IP"]
    for X, m in ((X_tr, m_tr), (X_va, m_va), (X_te, m_te)):
        assert list(m["flow_id"]) == list(X.index)
        assert list(m["Source IP"]) == list(truth.loc[X.index])
    label_of = feats.set_index("flow_id")["Label"]
    for X, y in ((X_tr, y_tr), (X_va, y_va), (X_te, y_te)):
        assert list(y.index) == list(X.index)
        assert list(y) == list(label_of.loc[X.index])


def test_split_no_overlap_sizes_and_columns():
    feats, meta = _split_inputs()
    X_tr, X_va, X_te, *_ = split_data(feats, meta, train_ratio=0.5, val_ratio=0.25, test_ratio=0.25, seed=1)
    ids = [set(X_tr.index), set(X_va.index), set(X_te.index)]
    assert not (ids[0] & ids[1]) and not (ids[0] & ids[2]) and not (ids[1] & ids[2])
    assert sum(len(i) for i in ids) == len(feats)
    for X in (X_tr, X_va, X_te):
        assert "flow_id" not in X.columns and "Label" not in X.columns


def test_split_is_deterministic():
    feats, meta = _split_inputs()
    a = split_data(feats, meta, seed=5)
    b = split_data(feats, meta, seed=5)
    for i in range(3):
        assert list(a[i].index) == list(b[i].index)


def test_split_removes_zero_day_holdout_labels():
    feats, meta = _split_inputs()
    extra = feats.iloc[:6].copy()
    extra["Label"] = "Heartbleed"
    extra["flow_id"] = np.arange(5000, 5006)
    feats2 = pd.concat([feats, extra], ignore_index=True)
    meta2 = pd.concat([meta, pd.DataFrame({"flow_id": extra["flow_id"], "Source IP": "1.1.1.1",
                                           "Timestamp": pd.Timestamp("2017-07-04")})], ignore_index=True)
    _, _, _, y_tr, y_va, y_te, *_ = split_data(feats2, meta2, seed=2)
    assert "Heartbleed" not in set(y_tr) | set(y_va) | set(y_te)


def test_time_aware_split_is_chronological():
    feats, meta = _split_inputs()
    X_tr, X_va, X_te, *_ = split_data(feats, meta, split_mode="time_aware",
                                      train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    ts = meta.set_index("flow_id")["Timestamp"]
    assert ts.loc[X_tr.index].max() <= ts.loc[X_va.index].min()
    assert ts.loc[X_va.index].max() <= ts.loc[X_te.index].min()


def test_split_errors():
    feats, meta = _split_inputs()
    with pytest.raises(ValueError):
        split_data(feats, meta.iloc[:-5], seed=1)                      # missing metadata rows
    with pytest.raises(ValueError):
        split_data(feats, meta, train_ratio=0.5, val_ratio=0.5, test_ratio=0.5)
    with pytest.raises(ValueError):
        split_data(feats, meta, split_mode="nope")


# ------------------------------------------------------------------- fit / transform
def _train_xy(n=500, seed=0):
    rng = np.random.RandomState(seed)
    y = pd.Series(rng.choice(["A", "B", "C"], size=n), name="Label")
    signal = y.map({"A": 0.0, "B": 2.0, "C": 4.0}).to_numpy() + rng.normal(0, 0.4, n)
    X = pd.DataFrame({
        "signal": signal,
        "signal_dup": signal * 5 - 3,           # correlated duplicate -> must be pruned
        "noise1": rng.normal(size=n),
        "noise2": rng.normal(size=n),
        "noise3": rng.normal(size=n),
    })
    X.loc[::17, "noise1"] = np.nan
    X.loc[3, "noise2"] = np.inf
    return X, y


def test_fit_prunes_correlated_and_mi_uses_labels():
    X, y = _train_xy()
    imputer, scaler, mask, sel = preprocess_train_fit(
        X, y, correlation_threshold=0.95, feature_selection_method="mutual_info",
        top_k_features=1, seed=3, return_selector=True)
    assert mask.dtype == bool and len(mask) == X.shape[1]
    assert list(X.columns[mask]) == ["signal"]
    assert sel.dropped_corr_ == {"signal_dup": "signal"}


def test_default_return_is_three_values_and_transform_works():
    X, y = _train_xy()
    out = preprocess_train_fit(X, y, correlation_threshold=0.95, feature_selection_method="none")
    assert len(out) == 3
    imputer, scaler, mask = out
    Z = preprocess_transform(X, imputer, scaler, mask)
    assert list(Z.columns) == ["signal", "noise1", "noise2", "noise3"]
    assert not np.isinf(Z.to_numpy()).any() and not np.isnan(Z.to_numpy()).any()
    assert list(Z.index) == list(X.index)


def test_correlation_pruning_can_be_disabled_with_threshold_one():
    X, y = _train_xy()
    _, _, mask = preprocess_train_fit(X, y, correlation_threshold=1.0, feature_selection_method="none")
    assert mask.all()


def test_variance_alias_still_works_and_respects_top_k():
    X, y = _train_xy()
    _, _, mask = preprocess_train_fit(X, y, feature_selection_method="variance", top_k_features=2)
    assert mask.sum() == 2


def test_fit_uses_train_statistics_only():
    X, y = _train_xy()
    train, other = X.iloc[:300], X.iloc[300:].copy()
    other["noise3"] = other["noise3"] + 1000.0                   # very different distribution
    imputer, scaler, mask = preprocess_train_fit(train, y.iloc[:300], feature_selection_method="none")
    idx = list(train.columns).index("noise3")
    assert scaler.mean_[idx] == pytest.approx(train["noise3"].mean(), abs=1e-6)
    Z = preprocess_transform(other, imputer, scaler, mask)
    assert Z["noise3"].mean() > 100                              # not re-centred on the other data


def test_fit_errors():
    X, y = _train_xy()
    with pytest.raises(ValueError):
        preprocess_train_fit(X, y.iloc[:-1])
    with pytest.raises(ValueError):
        preprocess_train_fit(X, y, feature_selection_method="tree_importance")


# --------------------------------------------------------------------- full pipeline
def _fake_dataset(rows_per_class=80, seed=0):
    rng = np.random.RandomState(seed)
    classes = sorted(EXPECTED_SUPERVISED_LABELS) + ["Heartbleed", "Infiltration"]
    labels = np.repeat(classes, rows_per_class)
    n = len(labels)
    base = rng.normal(size=(n, 6))
    shift = np.array([classes.index(c) % 7 for c in labels], dtype=float)[:, None] * 0.5
    cols = ["Destination Port", "Protocol", "Flow Duration", "Total Fwd Packets", "Flow Bytes/s", "Idle Max"]
    X = pd.DataFrame(np.abs(base + shift), columns=cols)
    X["Total Fwd Packets copy"] = X["Total Fwd Packets"] * 2.0          # correlated duplicate
    X["always_one"] = 1.0                                               # constant column
    X["Label"] = labels
    X["flow_id"] = np.arange(n) + 100
    X.loc[X["Label"] == "Web Attack", "Label"] = "Web Attack \x96 XSS"
    meta = pd.DataFrame({"flow_id": X["flow_id"], "Source IP": "10.0.0.1",
                         "Timestamp": pd.date_range("2017-07-03", periods=n, freq="s")})
    return X, meta


def test_full_pipeline_on_synthetic_data(monkeypatch):
    feats, meta = _fake_dataset()
    monkeypatch.setattr(pre, "load_reduced_data", lambda *a, **k: (feats.copy(), meta.copy()))
    res = pre.example_preprocessing_pipeline(save_outputs=False)

    labels = set(res["y_train"]) | set(res["y_val"]) | set(res["y_test"])
    assert labels == EXPECTED_SUPERVISED_LABELS
    assert set(res["holdout_features"]["Label"]) == {"Heartbleed", "Infiltration"}
    for key in ("X_train", "X_val", "X_test"):
        assert not {"flow_id", "Label"} & set(res[key].columns)
        assert res[key].index.name == "flow_id"
    sel = res["selector"]
    assert "always_one" in sel.dropped_constant_ or "always_one" not in res["X_train"].columns
    assert "Total Fwd Packets copy" in sel.dropped_corr_
    assert res["X_train"].shape[1] == len(sel.selected_)
    st = res["clean_stats"]
    assert st["rows_in"] - st["rows_removed_total"] == st["rows_out"]
    assert set(res["X_train"].index).isdisjoint(res["X_test"].index)
