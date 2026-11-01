"""Fit virtual-pressure and RO A/B parameters from instrumented bench sweeps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def fit_line(x: np.ndarray, y: np.ndarray) -> dict:
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    residual = y - fitted
    return {
        "intercept": float(intercept),
        "slope": float(slope),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "r2": float(1 - np.sum(residual**2) / max(np.sum((y - y.mean()) ** 2), 1e-12)),
        "n": int(len(x)),
    }


def fit_pump_current_pressure(frame: pd.DataFrame) -> dict:
    required = {"motor_current_a", "pressure_bar"}
    if not required.issubset(frame.columns):
        raise ValueError(f"required columns: {sorted(required)}")
    return fit_line(frame.motor_current_a.to_numpy(float), frame.pressure_bar.to_numpy(float))


def fit_ro_ab(frame: pd.DataFrame) -> dict:
    required = {"flux_lmh", "net_driving_pressure_bar", "feed_tds_mg_l", "permeate_tds_mg_l"}
    if not required.issubset(frame.columns):
        raise ValueError(f"required columns: {sorted(required)}")
    a_fit = fit_line(frame.net_driving_pressure_bar.to_numpy(float), frame.flux_lmh.to_numpy(float))
    a_value = max(0.0, a_fit["slope"])
    rejection = 1 - frame.permeate_tds_mg_l.to_numpy(float) / np.maximum(
        frame.feed_tds_mg_l.to_numpy(float), 1
    )
    b_values = (
        a_value * frame.flux_lmh.to_numpy(float) * (1 - rejection) / np.maximum(rejection, 1e-6)
    )
    return {
        "A_lmh_bar": a_value,
        "A_fit_rmse_lmh": a_fit["rmse"],
        "B_lmh_median": float(np.median(b_values)),
        "B_iqr_lmh": float(np.quantile(b_values, 0.75) - np.quantile(b_values, 0.25)),
        "n": int(len(frame)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--kind", choices=("pump", "ro"), required=True)
    args = parser.parse_args()
    source = pd.read_csv(args.csv)
    report = fit_pump_current_pressure(source) if args.kind == "pump" else fit_ro_ab(source)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
