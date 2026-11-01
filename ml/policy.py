"""Warning decision and evaluation helpers."""

from __future__ import annotations

import numpy as np


def failure_probability_from_rul(
    predicted_rul_days: np.ndarray, residual_sigma_days: float, horizon_days: float = 21
) -> np.ndarray:
    """Gaussian residual approximation; prediction equal to horizon implies 0.5 risk."""
    sigma = max(float(residual_sigma_days), 1.0)
    z = np.clip((np.asarray(predicted_rul_days) - horizon_days) / sigma, -30, 30)
    return 1 / (1 + np.exp(z))


def warning_mask(
    predicted_rul_days: np.ndarray, residual_sigma_days: float, tau: float, horizon_days: float = 21
) -> np.ndarray:
    """Warn where calibrated proxy probability meets validation-tuned tau."""
    if not 0 < tau < 1:
        raise ValueError("tau must be inside (0,1)")
    return (
        failure_probability_from_rul(predicted_rul_days, residual_sigma_days, horizon_days) >= tau
    )
