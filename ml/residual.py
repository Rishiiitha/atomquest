"""Gradient-boosted correction model for state-projection residuals."""

from sklearn.ensemble import HistGradientBoostingRegressor


def make_residual_model(seed: int = 20261101) -> HistGradientBoostingRegressor:
    """Small CPU model; all hyperparameters are fixed before the OOD run."""
    return HistGradientBoostingRegressor(
        max_iter=90,
        learning_rate=0.08,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=seed,
    )
