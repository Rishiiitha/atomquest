"""Small two-state health/rate Kalman filter implemented locally."""

from __future__ import annotations

import numpy as np


class ScalarHealthEKF:
    """Track a decreasing health scalar and nonnegative damage rate.

    Hand trace: start h=.9, rate=.01/day, threshold=.6 -> projected 30 days.
    One day later the state prediction is h=.89; a measurement of .90 nudges it
    upward according to the Kalman gain while the damage rate remains positive.
    This is a simple extended-Kalman-style linear state model, not a product model.
    """

    def __init__(
        self, initial_health: float, initial_rate: float = 0.002, measurement_var: float = 0.0025
    ):
        self.x = np.array([float(initial_health), max(1e-5, float(initial_rate))])
        self.p = np.diag([0.03, 0.0003]).astype(float)
        self.q = np.diag([0.0004, 0.000003]).astype(float)
        self.r = float(measurement_var)

    def update(self, measurement: float, dt_days: float = 1.0) -> tuple[float, float]:
        transition = np.array([[1.0, -dt_days], [0.0, 1.0]])
        predicted = transition @ self.x
        covariance = transition @ self.p @ transition.T + self.q
        observation = np.array([1.0, 0.0])
        innovation = float(measurement - observation @ predicted)
        innovation_var = float(observation @ covariance @ observation.T + self.r)
        gain = covariance @ observation.T / innovation_var
        self.x = predicted + gain * innovation
        self.x[0] = float(np.clip(self.x[0], 0, 1.2))
        self.x[1] = float(np.clip(self.x[1], 1e-5, 0.2))
        self.p = (np.eye(2) - np.outer(gain, observation)) @ covariance
        return float(self.x[0]), float(self.x[1])

    def project_rul_days(self, threshold: float) -> float:
        """Project the latent health linearly to threshold; at .9/.01/.6 -> 30 days."""
        return max(0.0, min(1000.0, (self.x[0] - threshold) / max(self.x[1], 1e-5)))
