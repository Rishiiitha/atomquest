"""Convert bench CSV sensor columns to the twin's documented Parquet schema."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from twin.physics import normalized_permeability_lmh_bar, osmotic_pressure_bar, virtual_pressure_bar

REQUIRED = {
    "timestamp",
    "unit_id",
    "inlet_tds_mg_l",
    "outlet_tds_mg_l",
    "turbidity_ntu",
    "temp_c",
    "flow_l_h",
    "motor_current_a",
    "rpm",
    "pump_runtime_h",
    "litres_dispensed_l",
    "inlet_pressure_bar",
}


def adapt_frame(source: pd.DataFrame, area_m2: float = 0.4) -> pd.DataFrame:
    """Map required sensor channels; derived estimates are identified by column name."""
    missing = REQUIRED - set(source.columns)
    if missing:
        raise ValueError(f"bench CSV is missing required columns: {', '.join(sorted(missing))}")
    frame = source.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise", utc=True)
    frame = frame.sort_values(["unit_id", "timestamp"]).reset_index(drop=True)
    frame["day"] = frame.groupby("unit_id").cumcount().astype(float)
    frame["scenario"] = "bench_import"
    frame["hardness"] = np.nan
    frame["fill_time_h"] = 1.0
    frame["current_ripple_a"] = 0.0
    frame["pump_runtime_h"] = pd.to_numeric(frame["pump_runtime_h"], errors="raise")
    frame["litres_dispensed_l"] = pd.to_numeric(frame["litres_dispensed_l"], errors="raise")
    frame["cumulative_litres"] = frame.groupby("unit_id")["litres_dispensed_l"].cumsum()
    frame["pressure_virtual_bar"] = frame["motor_current_a"].map(virtual_pressure_bar)
    frame["osmotic_pressure_bar"] = frame["inlet_tds_mg_l"].map(osmotic_pressure_bar)
    frame["ro_permeability_est_lmh_bar"] = [
        normalized_permeability_lmh_bar(q / area_m2, p, tds, temp)
        for q, p, tds, temp in zip(
            frame.flow_l_h,
            frame.pressure_virtual_bar,
            frame.inlet_tds_mg_l,
            frame.temp_c,
            strict=True,
        )
    ]
    frame["raw_resistance_proxy"] = (frame["pressure_virtual_bar"] + 0.1) / frame["flow_l_h"].clip(
        lower=0.1
    )
    frame["carbon_exposure_index"] = frame["cumulative_litres"] * 0.3 / 4000
    frame["ro_rejection_fraction"] = 1 - frame["outlet_tds_mg_l"] / frame["inlet_tds_mg_l"].clip(
        lower=1
    )
    frame["hydraulic_resistance_index"] = frame["raw_resistance_proxy"]
    frame["inlet_pressure_bar"] = pd.to_numeric(frame["inlet_pressure_bar"], errors="raise")
    frame["flow_l_h"] = pd.to_numeric(frame["flow_l_h"], errors="raise")
    frame["motor_current_a"] = pd.to_numeric(frame["motor_current_a"], errors="raise")
    frame["rpm"] = pd.to_numeric(frame["rpm"], errors="raise")
    frame["outlet_tds_mg_l"] = pd.to_numeric(frame["outlet_tds_mg_l"], errors="raise")
    frame["tds_in_mg_l"] = pd.to_numeric(frame["inlet_tds_mg_l"], errors="raise")
    frame["litres_dispensed_l"] = pd.to_numeric(frame["litres_dispensed_l"], errors="raise")
    frame["pump_runtime_h"] = pd.to_numeric(frame["pump_runtime_h"], errors="raise")
    frame["pressure_virtual_bar"] = pd.to_numeric(frame["pressure_virtual_bar"], errors="raise")
    frame["current_ripple_a"] = pd.to_numeric(frame["current_ripple_a"], errors="raise")
    frame["flow_l_h"] = frame["flow_l_h"].clip(lower=0)
    return frame


def convert_csv(source_path: Path, output_path: Path) -> pd.DataFrame:
    frame = adapt_frame(pd.read_csv(source_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    converted = convert_csv(args.source, args.output)
    print(f"converted {len(converted)} rows; source provenance must be recorded by caller")


if __name__ == "__main__":
    main()
