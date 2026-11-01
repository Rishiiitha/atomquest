"""Small deterministic sensor effects; production defaults are in sensors.yaml."""

from __future__ import annotations

import numpy as np


def noisy_reading(value: float, sigma: float, rng: np.random.Generator) -> float:
    """Add a zero-mean Gaussian instrument error; value=10, sigma=1 has expected reading 10."""
    if sigma < 0:
        raise ValueError("sigma must be nonnegative")
    return float(value + rng.normal(0, sigma))


def quantize(value: float, step: float) -> float:
    """Round to the nearest instrument step; 1.24 at step .1 becomes 1.2."""
    if step <= 0:
        raise ValueError("step must be positive")
    return round(value / step) * step
