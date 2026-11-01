"""Simple status-quo and raw-feature baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ml.features import model_features


def fit_raw_baseline(train: pd.DataFrame, stage: str, seed: int) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(
        max_iter=80, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=1.0, random_state=seed
    )
    X = model_features(train, physics=False)
    y = train[f"rul_{stage}_d"].astype(float)
    if len(X) > 120_000:
        keep = np.linspace(0, len(X) - 1, 120_000).astype(int)
        X, y = X.iloc[keep], y.iloc[keep]
    return model.fit(X, y)


def fixed_schedule_prediction(stage: str, age_days: pd.Series, train: pd.DataFrame) -> np.ndarray:
    """Time-counter baseline uses the train cohort's median functional life."""
    life = float(train[f"life_{stage}_d"].median())
    return np.maximum(0.0, life - age_days.to_numpy(dtype=float))
