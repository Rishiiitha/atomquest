"""Leakage-aware feature preparation for physics-guided and raw baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.estimator import ScalarHealthEKF
from twin.simulator import FEATURES_RAW, THRESHOLDS

TARGETS = ["sediment", "uf", "carbon", "ro"]
THRESHOLD = {
    name: THRESHOLDS[
        f"{name}_{'breakthrough_ratio' if name == 'carbon' else 'permeability_fraction' if name == 'ro' else 'health'}"
    ]["value"]
    for name in TARGETS
}
THRESHOLD["carbon"] = 1 - THRESHOLDS["carbon_breakthrough_ratio"]["value"]


TIER_RAW = {
    "A": [
        "outlet_tds_mg_l",
        "pump_runtime_h",
        "litres_dispensed_l",
        "motor_current_a",
        "rpm",
        "day",
    ],
    "B": [
        "outlet_tds_mg_l",
        "pump_runtime_h",
        "litres_dispensed_l",
        "motor_current_a",
        "rpm",
        "day",
        "tds_in_mg_l",
        "flow_l_h",
        "temp_c",
    ],
    "C": FEATURES_RAW,
}
TIER_PHYS = {
    "A": ["pressure_virtual_bar", "carbon_exposure_index"],
    "B": [
        "pressure_virtual_bar",
        "osmotic_pressure_bar",
        "ro_permeability_est_lmh_bar",
        "raw_resistance_proxy",
        "carbon_exposure_index",
        "ro_rejection_fraction",
        "hydraulic_resistance_index",
    ],
    "C": [
        "pressure_virtual_bar",
        "osmotic_pressure_bar",
        "ro_permeability_est_lmh_bar",
        "raw_resistance_proxy",
        "carbon_exposure_index",
        "ro_rejection_fraction",
        "hydraulic_resistance_index",
    ],
}


def model_features(
    frame: pd.DataFrame, physics: bool = True, tier: str = "C", stage: str | None = None
) -> pd.DataFrame:
    """Build only observed, sensor-derived inputs (never use *_true or RUL labels)."""
    if tier not in TIER_RAW:
        raise ValueError("telemetry tier must be A, B, or C")
    names = TIER_RAW[tier] + (TIER_PHYS[tier] if physics else [])
    chosen = frame[names].copy()
    if physics and stage:
        chosen["ekf_state_rul"] = frame[f"ekf_rul_{stage}_{tier}_d"].to_numpy(dtype=float)
    return chosen.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_state_projections(frame: pd.DataFrame) -> pd.DataFrame:
    """Add EKF state-based RUL projections for each held-out unit chronology."""
    out = frame.copy()
    for tier in TIER_RAW:
        for stage in TARGETS:
            out[f"ekf_rul_{stage}_{tier}_d"] = 0.0
            if tier == "C":
                out[f"ekf_rul_{stage}_d"] = 0.0
    for _, indices in out.groupby("unit_id", sort=False).groups.items():
        idx = np.asarray(list(indices), dtype=int)
        unit = out.loc[idx].sort_values("day")
        first_resistance = max(
            float(unit["raw_resistance_proxy"].iloc[: min(7, len(unit))].median()), 1e-4
        )
        resistance_ratio = np.clip(
            unit["raw_resistance_proxy"].to_numpy() / first_resistance, 0.25, 8
        )
        # This shared hydraulic proxy cannot uniquely separate sediment from UF.
        hydraulic_health_bc = np.clip(1 - 0.16 * np.log(resistance_ratio), 0.05, 1.0)
        motor_load = unit["motor_current_a"].to_numpy() / np.maximum(unit["rpm"].to_numpy(), 1)
        motor_load_baseline = max(float(np.median(motor_load[: min(7, len(motor_load))])), 1e-8)
        hydraulic_health_a = np.clip(
            1 - 0.16 * np.log(np.clip(motor_load / motor_load_baseline, 0.25, 8)), 0.05, 1.0
        )
        exposure_health = np.clip(1 - unit["carbon_exposure_index"].to_numpy(), 0.02, 1.0)
        ro_health_bc = np.clip(unit["ro_permeability_est_lmh_bar"].to_numpy() / 8.0, 0.01, 1.2)
        outlet = unit["outlet_tds_mg_l"].to_numpy()
        outlet_base = max(float(np.median(outlet[: min(7, len(outlet))])), 1.0)
        ro_health_a = np.clip(1 - 0.25 * np.maximum(0, outlet / outlet_base - 1), 0.01, 1.0)
        sorted_idx = unit.index.to_numpy()
        observations_by_tier = {
            "A": {
                "sediment": hydraulic_health_a,
                "uf": hydraulic_health_a,
                "carbon": exposure_health,
                "ro": ro_health_a,
            },
            "B": {
                "sediment": hydraulic_health_bc,
                "uf": hydraulic_health_bc,
                "carbon": exposure_health,
                "ro": ro_health_bc,
            },
            "C": {
                "sediment": hydraulic_health_bc,
                "uf": hydraulic_health_bc,
                "carbon": exposure_health,
                "ro": ro_health_bc,
            },
        }
        for tier, observations in observations_by_tier.items():
            for stage in TARGETS:
                values = observations[stage]
                ekf = ScalarHealthEKF(values[0], initial_rate=0.002)
                estimates = np.empty(len(values))
                for j, measurement in enumerate(values):
                    if j:
                        ekf.update(float(measurement))
                    estimates[j] = ekf.project_rul_days(THRESHOLD[stage])
                out.loc[sorted_idx, f"ekf_rul_{stage}_{tier}_d"] = estimates
                if tier == "C":
                    out.loc[sorted_idx, f"ekf_rul_{stage}_d"] = estimates
    return out


def training_matrix(
    frame: pd.DataFrame, stage: str, physics: bool = True
) -> tuple[pd.DataFrame, pd.Series]:
    """Return input matrix and residual target for the physics-guided corrector."""
    X = model_features(frame, physics=physics, stage=stage if physics else None)
    y = frame[f"rul_{stage}_d"].astype(float)
    return X, y


def split_conformal_radius(errors: np.ndarray, coverage: float = 0.9) -> float:
    """Finite-sample split-conformal absolute-residual radius."""
    values = np.sort(np.abs(np.asarray(errors, dtype=float)))
    if values.size == 0 or not 0 < coverage < 1:
        raise ValueError("nonempty calibration errors and coverage in (0, 1) are required")
    rank = min(values.size, int(np.ceil((values.size + 1) * coverage)))
    return float(values[rank - 1])
