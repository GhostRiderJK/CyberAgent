"""Leakage-safe feature selection for CyberAgent.

Fit on the TRAINING set only, then reuse ``transform`` on val/test/holdout.

Steps (in order):
  1. Drop constant columns.
  2. Correlation pruning: walk the columns in order and drop a column when it
     correlates above ``corr_threshold`` with an already-kept column. The kept
     partner is recorded so the choice can be explained. A threshold >= 1.0
     disables this step.
  3. Mutual-information top-K using y_train (skipped when top_k is None or
     there are not more than top_k columns left).

Usage::

    sel = FeatureSelector(corr_threshold=0.95, top_k=40, seed=42)
    sel.fit(X_train, y_train)
    X_train_s = sel.transform(X_train)
    X_val_s = sel.transform(X_val)
    sel.save_report("results/tables/selected_features.csv")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

logger = logging.getLogger("cyberagent")


class FeatureSelector:
    def __init__(
        self,
        corr_threshold: float = 0.95,
        top_k: Optional[int] = 40,
        mi_sample_size: int = 50_000,
        seed: int = 42,
    ) -> None:
        self.corr_threshold = corr_threshold
        self.top_k = top_k
        self.mi_sample_size = mi_sample_size
        self.seed = seed

        self.columns_in_: List[str] = []
        self.dropped_constant_: List[str] = []
        self.dropped_corr_: Dict[str, str] = {}  # dropped column -> kept partner
        self.dropped_selection_: List[str] = []
        self.mi_scores_: Dict[str, float] = {}
        self.selected_: List[str] = []
        self._fitted = False

    # ------------------------------------------------------------------ fit
    def fit(self, X: pd.DataFrame, y) -> "FeatureSelector":
        if len(X) != len(y):
            raise ValueError("X and y must have the same length")
        X = X.copy()
        self.columns_in_ = list(X.columns)
        self.dropped_constant_, self.dropped_corr_ = [], {}
        self.dropped_selection_, self.mi_scores_ = [], {}

        # 1. constant columns (NaN ignored)
        self.dropped_constant_ = [c for c in X.columns if X[c].nunique(dropna=True) <= 1]
        kept = [c for c in X.columns if c not in self.dropped_constant_]

        # 2. correlation pruning (median-filled copy; X itself is not modified)
        #    A threshold >= 1.0 disables pruning.
        filled = X[kept].fillna(X[kept].median())
        kept_after_corr: List[str] = []
        if self.corr_threshold >= 1.0:
            kept_after_corr = list(kept)
        else:
            corr = filled.corr().abs().fillna(0.0)
            for col in kept:
                if kept_after_corr:
                    sims = corr.loc[col, kept_after_corr]
                    if sims.max() > self.corr_threshold:
                        self.dropped_corr_[col] = str(sims.idxmax())
                        continue
                kept_after_corr.append(col)

        # 3. mutual information top-K, using y_train
        selected = list(kept_after_corr)
        if self.top_k is not None and len(kept_after_corr) > self.top_k:
            sub = filled[kept_after_corr]
            y_arr = np.asarray(y)
            if len(sub) > self.mi_sample_size:
                rng = np.random.RandomState(self.seed)
                idx = rng.choice(len(sub), self.mi_sample_size, replace=False)
                sub, y_arr = sub.iloc[idx], y_arr[idx]
            try:
                scores = mutual_info_classif(
                    sub, y_arr,
                    n_neighbors=max(1, min(3, len(sub) - 1)),
                    random_state=self.seed,
                )
            except ValueError as exc:  # e.g. too few samples
                logger.warning("Mutual information failed (%s); ranking by variance instead", exc)
                scores = sub.var().to_numpy()
            self.mi_scores_ = dict(zip(kept_after_corr, map(float, scores)))
            ranked = sorted(kept_after_corr, key=lambda c: (-self.mi_scores_[c], c))
            top = set(ranked[: self.top_k])
            selected = [c for c in kept_after_corr if c in top]  # keep original order
            self.dropped_selection_ = [c for c in kept_after_corr if c not in top]

        self.selected_ = selected
        self._fitted = True
        logger.info(
            "Feature selection: %d in, %d constant, %d correlated, %d low-MI, %d kept",
            len(self.columns_in_), len(self.dropped_constant_), len(self.dropped_corr_),
            len(self.dropped_selection_), len(self.selected_),
        )
        return self

    # ------------------------------------------------------------ transform
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("FeatureSelector must be fitted first")
        missing = [c for c in self.selected_ if c not in X.columns]
        if missing:
            raise KeyError(f"Missing columns at transform time: {missing[:5]}")
        return X[self.selected_]

    def fit_transform(self, X: pd.DataFrame, y) -> pd.DataFrame:
        return self.fit(X, y).transform(X)

    # --------------------------------------------------------------- report
    def report(self) -> pd.DataFrame:
        rows = []
        for c in self.columns_in_:
            if c in self.dropped_constant_:
                status, reason, partner = "dropped", "constant", ""
            elif c in self.dropped_corr_:
                status, reason, partner = "dropped", "correlated", self.dropped_corr_[c]
            elif c in self.dropped_selection_:
                status, reason, partner = "dropped", "low_mutual_information", ""
            else:
                status, reason, partner = "kept", "", ""
            rows.append({
                "feature": c, "status": status, "reason": reason,
                "kept_partner": partner, "mi_score": self.mi_scores_.get(c, np.nan),
            })
        return pd.DataFrame(rows)

    def save_report(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.report().to_csv(path, index=False)
        return path
