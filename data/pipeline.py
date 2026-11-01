"""Deterministic generation, training, calibration and evidence export."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.baselines import fit_raw_baseline, fixed_schedule_prediction
from ml.features import (
    TARGETS,
    TIER_PHYS,
    TIER_RAW,
    add_state_projections,
    model_features,
    split_conformal_radius,
)
from ml.residual import make_residual_model
from twin.simulator import (
    SCENARIOS,
    SEED,
    generate_cohort,
    read_config,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DATA = ROOT / "data" / "generated"
STAGES = TARGETS
HORIZONS = (30, 21, 14)
MODELS: dict[str, dict[str, object]] = {stage: {} for stage in STAGES}


def _sample(frame: pd.DataFrame, max_rows: int = 120_000, seed: int = SEED) -> pd.DataFrame:
    if len(frame) <= max_rows:
        return frame
    rng = np.random.default_rng(seed)
    return frame.iloc[np.sort(rng.choice(len(frame), size=max_rows, replace=False))]


def _truth_horizon(frame: pd.DataFrame, stage: str, horizon: int) -> pd.DataFrame:
    selected = []
    for _, unit in frame.groupby("unit_id", sort=False):
        eligible = unit.loc[unit[f"rul_{stage}_d"] >= horizon]
        if len(eligible):
            row = eligible.iloc[(eligible[f"rul_{stage}_d"] - horizon).abs().argmin()]
            selected.append(row)
    return pd.DataFrame(selected) if selected else frame.iloc[:0]


def _nasa_score(errors: np.ndarray) -> float:
    # NASA's asymmetric PHM score: under-prediction (too late) gets steeper cost.
    value = np.where(
        errors < 0,
        np.exp(np.clip(-errors / 13, -50, 50)) - 1,
        np.exp(np.clip(errors / 10, -50, 50)) - 1,
    )
    return float(np.mean(value)) if len(value) else math.nan


def _horizon_stats(
    frame: pd.DataFrame, stage: str, pred_col: str, interval_q: dict | float | None = None
) -> dict:
    results = {}
    for horizon in HORIZONS:
        sample = _truth_horizon(frame, stage, horizon)
        true = sample[f"rul_{stage}_d"].to_numpy(dtype=float)
        pred = sample[pred_col].to_numpy(dtype=float)
        error = pred - true
        one = {
            "n_units": int(len(sample)),
            "mae_days": float(np.mean(np.abs(error))) if len(error) else None,
            "median_absolute_error_days": float(np.median(np.abs(error))) if len(error) else None,
            "mean_absolute_relative_error": float(np.mean(np.abs(error) / np.maximum(true, 1)))
            if len(error)
            else None,
            "nasa_score": _nasa_score(error),
            "mae_litres": float(np.mean(np.abs(error) * sample["litres_dispensed_l"].to_numpy()))
            if len(error)
            else None,
        }
        q = interval_q.get(str(horizon), 0.0) if isinstance(interval_q, dict) else interval_q
        if q is not None and len(error):
            one["conformal_q_days"] = q
            one["coverage"] = float(np.mean(np.abs(error) <= q))
            one["mean_interval_width_days"] = 2 * q
        results[str(horizon)] = one
    return results


def _first_warning_events(
    frame: pd.DataFrame, stage: str, pred_col: str, tau: float, sigma: float
) -> list[dict]:
    events = []
    for unit_id, unit in frame.groupby("unit_id", sort=False):
        unit = unit.sort_values("day")
        prob = 1 / (1 + np.exp(np.clip((unit[pred_col].to_numpy() - 21) / max(sigma, 1), -30, 30)))
        hits = np.flatnonzero(prob >= tau)
        if len(hits):
            idx = int(hits[0])
            events.append(
                {
                    "unit_id": unit_id,
                    "day": int(unit["day"].iloc[idx]),
                    "true_rul_d": float(unit[f"rul_{stage}_d"].iloc[idx]),
                    "predicted_rul_d": float(unit[pred_col].iloc[idx]),
                }
            )
    return events


def _warning_summary(frame: pd.DataFrame, stage: str, events: list[dict]) -> dict:
    count = len(frame["unit_id"].unique())
    years = max(frame.groupby("unit_id")["day"].max().mean() / 365, 1e-3)
    false = [e for e in events if e["true_rul_d"] > 21]
    useful = [e for e in events if 0 <= e["true_rul_d"] <= 21]
    missed = count - len(events)
    return {
        "units": count,
        "first_warning_events": len(events),
        "false_alarms_per_unit_year": len(false) / max(count * years, 1e-9),
        "false_alarm_early_event_fraction": len(false) / max(len(events), 1),
        "missed_failure_fraction": missed / max(count, 1),
        "lead_time_days_median": float(np.median([e["true_rul_d"] for e in useful]))
        if useful
        else None,
        "lead_time_days_p10": float(np.quantile([e["true_rul_d"] for e in useful], 0.1))
        if useful
        else None,
        "lead_time_days_p90": float(np.quantile([e["true_rul_d"] for e in useful], 0.9))
        if useful
        else None,
    }


def _signature_matrix() -> dict:
    """Compare ten single causes and two pairs under two assumed controller modes."""
    from twin.physics import current_from_pressure_a, normalized_permeability_lmh_bar, ro_flux_lmh

    cfg = read_config("physics.yaml")
    ro, pump, tank = cfg["ro"], cfg["pump"], cfg["tank"]
    area = float(ro["area_m2"]["value"])
    base_rpm = float(pump["rpm"]["value"])
    params = {
        "p": 4.5,
        "tds": 600.0,
        "temp": 25.0,
        "a": float(ro["permeability_lmh_bar"]["value"]),
        "b": float(ro["salt_passage_lmh"]["value"]),
        "flow_scale": 1.0,
        "wear": 0.0,
        "pperm": float(tank["nominal_permeate_pressure_bar"]["value"]),
    }

    def observe(
        controller: str,
        p: float,
        tds: float,
        temp: float,
        a: float,
        b: float,
        flow_scale: float = 1.0,
        wear: float = 0.0,
        pperm: float | None = None,
    ) -> dict:
        backpressure = params["pperm"] if pperm is None else pperm
        flux = ro_flux_lmh(
            a,
            p,
            tds,
            temp,
            backpressure,
            float(ro["cp_factor"]["value"]),
            float(ro["osmotic_bar_per_g_l"]["value"]),
            float(ro["temp_coefficient_per_c"]["value"]),
        )
        rpm = (
            base_rpm * (1 - wear * float(pump["rpm_wear_fraction"]["value"]))
            if controller == "fixed_duty"
            else base_rpm
        )
        flow = flux * area * flow_scale * (rpm / base_rpm) * (1 - wear)
        current = current_from_pressure_a(
            p,
            float(pump["current_intercept_a"]["value"]),
            float(pump["current_slope_a_bar"]["value"]),
        )
        if controller == "speed_regulated":
            current += wear * float(pump["current_wear_increment_a"]["value"])
        return {
            "flow_l_h": flow,
            "fill_time_h": float(tank["usable_storage_l"]["value"]) / max(flow, 0.1),
            "current_a": current,
            "rpm": rpm,
            "current_ripple_a": float(cfg["simulation"]["ro_base_ripple_a"]["value"])
            + (1 - min(flow_scale, 1))
            * float(cfg["simulation"]["ripple_starvation_gain_a"]["value"])
            + wear * float(cfg["simulation"]["ripple_wear_gain_a"]["value"]),
            "outlet_tds_mg_l": tds * (1 - (1 - b / max(b + a * flux, 1e-9))),
            "pressure_bar": p,
            "normalised_permeability": normalized_permeability_lmh_bar(
                flow / area,
                p,
                tds,
                temp,
                backpressure,
                float(ro["cp_factor"]["value"]),
                float(ro["osmotic_bar_per_g_l"]["value"]),
                float(ro["temp_coefficient_per_c"]["value"]),
            ),
        }

    conditions = {
        "high_tds": {"tds": 1800.0},
        "cold_water": {"temp": 15.0},
        "ro_fouling": {"a": 5.6},
        "ro_scaling": {"a": 6.8, "b": 1.5, "tds": 1450.0},
        "chlorine_damage": {"b": 2.6},
        "pump_wear": {"wear": 0.18},
        "sediment_restriction": {"p": 4.2, "flow_scale": 0.82},
        "uf_restriction": {"p": 4.3, "flow_scale": 0.88},
        "low_inlet_pressure": {"p": 4.0, "flow_scale": 0.97},
        "tank_backpressure": {"pperm": 0.5},
        "pair_sediment_and_ro_fouling": {"p": 4.2, "flow_scale": 0.82, "a": 5.6},
        "pair_chlorine_and_ro_fouling": {"a": 5.6, "b": 2.6},
    }
    outputs = (
        "flow_l_h",
        "fill_time_h",
        "current_a",
        "rpm",
        "current_ripple_a",
        "outlet_tds_mg_l",
        "pressure_bar",
        "normalised_permeability",
    )
    baseline_by_mode, rows = {}, {}
    for controller in ("fixed_duty", "speed_regulated"):
        nominal = observe(controller, **params)
        baseline_by_mode[controller] = nominal
        for name, changes in conditions.items():
            observation = observe(controller, **(params | changes))
            rows[f"{controller}:{name}"] = {
                key: round(float(observation[key] - nominal[key]), 6) for key in outputs
            }
    return {
        "provenance": "SIMULATED",
        "baseline_by_controller": baseline_by_mode,
        "controller_modes": ["fixed_duty", "speed_regulated"],
        "delta_from_baseline": rows,
        "conditions": list(conditions),
        "interpretation": "Controlled equation perturbations under two simplified controller assumptions; hypotheses for bench verification, not hardware facts.",
    }


def _business_impact(test: pd.DataFrame, pred: dict[str, np.ndarray], warning_policy: dict) -> dict:
    """Monte Carlo policy comparison from simulated unit lives; fixed assumptions are exposed."""
    rng = np.random.default_rng(SEED + 55)
    sampled_ids = list(test["unit_id"].unique())
    rows = []
    for unit_id in sampled_ids:
        unit = test.loc[test.unit_id == unit_id]
        rows.append(unit.iloc[0])
    profiles: list[dict[str, Any]] = []
    for _, row in pd.DataFrame(rows).iterrows():
        profile: dict[str, Any] = {"daily_l": float(row["litres_dispensed_l"])}
        unit = test.loc[test.unit_id == row["unit_id"]].sort_values("day")
        for stage in STAGES:
            truth = unit[f"rul_{stage}_d"].to_numpy()
            life = int(unit[f"life_{stage}_d"].iloc[0])
            if life <= 0:
                continue
            p = pred[stage][unit.index.to_numpy()]
            sigma = float(warning_policy[stage]["validation_residual_sigma_days"])
            risk = 1 / (1 + np.exp(np.clip((p - 21) / max(sigma, 1.0), -30, 30)))
            triggered = np.flatnonzero(risk >= warning_policy[stage]["tau"])
            useful_alarm = bool(len(triggered) and 0 <= float(truth[int(triggered[0])]) <= 21)
            action_age = int(triggered[0]) if useful_alarm else life + 30
            profile[stage] = {
                "life": life,
                "model_action_age": action_age,
                "life_l": float(unit[f"rul_{stage}_l"].iloc[0]),
            }
        profiles.append(profile)

    households = 1000
    days = 3 * 365
    policies: dict[str, list[dict[str, float]]] = {
        "fixed_schedule": [],
        "volume_counter": [],
        "filtertwin": [],
    }
    replacement_fraction = float(
        read_config("model.yaml")["estimator"]["business_replacement_fraction"]
    )
    assumptions = {
        "replacement_fraction_of_median_life": replacement_fraction,
        "horizon_years": 3,
        "households": households,
    }
    median_life_volume = {
        stage: float(np.median([p[stage]["life_l"] for p in profiles])) for stage in STAGES
    }
    for _ in range(households):
        base = profiles[int(rng.integers(0, len(profiles)))]
        for stage in STAGES:
            data = base[stage]
            life = max(1, data["life"])
            schedule_age = replacement_fraction * float(
                np.median([p[stage]["life"] for p in profiles])
            )
            volume_age = replacement_fraction * median_life_volume[stage] / max(base["daily_l"], 1)
            warning_age = data["model_action_age"]
            for name, replacement_age in (
                ("fixed_schedule", schedule_age),
                ("volume_counter", volume_age),
                ("filtertwin", warning_age),
            ):
                action = max(1.0, replacement_age)
                cycles = int(math.ceil(days / min(action, life)))
                life_wasted = max(0.0, life - action) / life
                failed = cycles if action > life else 0
                policies[name].append({"wasted": life_wasted, "failed": failed, "cycles": cycles})
    summary = {}
    for name, entries in policies.items():
        summary[name] = {
            "mean_useful_life_wasted_fraction": float(np.mean([x["wasted"] for x in entries])),
            "cartridge_failures_per_1000_households_3y": int(sum(x["failed"] for x in entries)),
            "replacements_per_1000_households_3y": int(sum(x["cycles"] for x in entries)),
            "cartridges_failing_before_replacement_fraction": float(
                sum(x["failed"] for x in entries) / max(sum(x["cycles"] for x in entries), 1)
            ),
        }
    fixed_failures = summary["fixed_schedule"]["cartridge_failures_per_1000_households_3y"]
    avoided = fixed_failures - summary["filtertwin"]["cartridge_failures_per_1000_households_3y"]
    summary["filtertwin"]["unexpected_failures_avoided_vs_fixed"] = avoided
    summary["filtertwin"]["downtime_events_avoided_vs_fixed"] = avoided
    return {"provenance": "SIMULATED", "assumptions": assumptions, "policies": summary}


def _write_generated_bench_samples(test: pd.DataFrame) -> dict:
    """Export a small, explicitly synthetic adapter and calibration fixture."""
    sample_dir = ROOT / "hardware" / "samples"
    web_dir = ROOT / "web" / "public" / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)
    first_unit = test.sort_values(["unit_id", "day"]).unit_id.iloc[0]
    unit = (
        test.loc[test.unit_id == first_unit]
        .sort_values("day")
        .head(24)
        .reset_index(drop=True)
        .copy()
    )
    unit["timestamp"] = pd.date_range("2025-01-01", periods=len(unit), freq="D", tz="UTC").astype(
        str
    )
    unit["unit_id"] = "SIMULATED-BENCH-LIKE-001"
    columns = [
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
    ]
    bench = unit.rename(columns={"tds_in_mg_l": "inlet_tds_mg_l"})[columns]
    sample_path = sample_dir / "bench_like.csv"
    bench.to_csv(sample_path, index=False)
    shutil.copyfile(sample_path, web_dir / "bench_like.csv")

    physical = read_config("physics.yaml")
    ro = physical["ro"]
    pump = physical["pump"]
    sweep = physical["calibration_sweep"]
    pressure = np.linspace(
        float(sweep["pressure_bar_min"]["value"]),
        float(sweep["pressure_bar_max"]["value"]),
        int(sweep["points"]["value"]),
    )
    feed_tds = float(sweep["feed_tds_mg_l"]["value"])
    temperature = float(sweep["temperature_c"]["value"])
    permeability = float(ro["permeability_lmh_bar"]["value"])
    salt_passage = float(ro["salt_passage_lmh"]["value"])
    permeate_pressure = float(ro["permeate_backpressure_bar"]["value"])
    cp = float(ro["cp_factor"]["value"])
    osmotic_coeff = float(ro["osmotic_bar_per_g_l"]["value"])
    temp_coeff = float(ro["temp_coefficient_per_c"]["value"])
    from twin.physics import current_from_pressure_a, osmotic_pressure_bar, ro_flux_lmh

    rng = np.random.default_rng(SEED + 818)
    flux = np.array(
        [
            ro_flux_lmh(
                permeability,
                p,
                feed_tds,
                temperature,
                permeate_pressure,
                cp,
                osmotic_coeff,
                temp_coeff,
            )
            for p in pressure
        ]
    )
    rejection = permeability * flux / (permeability * flux + salt_passage)
    calibration = pd.DataFrame(
        {
            "motor_current_a": [
                current_from_pressure_a(
                    p,
                    float(pump["current_intercept_a"]["value"]),
                    float(pump["current_slope_a_bar"]["value"]),
                )
                + rng.normal(0, float(sweep["current_noise_sigma_a"]["value"]))
                for p in pressure
            ],
            "pressure_bar": pressure
            + rng.normal(0, float(sweep["pressure_noise_sigma_bar"]["value"]), size=len(pressure)),
            "flux_lmh": flux
            + rng.normal(0, float(sweep["flux_noise_sigma_lmh"]["value"]), size=len(pressure)),
            "net_driving_pressure_bar": pressure
            - permeate_pressure
            - osmotic_pressure_bar(feed_tds, cp, osmotic_coeff)
            + rng.normal(0, float(sweep["pressure_noise_sigma_bar"]["value"]), size=len(pressure)),
            "feed_tds_mg_l": feed_tds,
            "permeate_tds_mg_l": feed_tds * (1 - rejection)
            + rng.normal(
                0, float(sweep["permeate_tds_noise_sigma_mg_l"]["value"]), size=len(pressure)
            ),
        }
    )
    calibration_path = sample_dir / "bench_like_calibration.csv"
    calibration.to_csv(calibration_path, index=False)
    from hardware.calibration.fit_calibration import fit_pump_current_pressure, fit_ro_ab

    fits = {
        "provenance": "SIMULATED",
        "rows": int(len(calibration)),
        "pump_current_to_pressure": fit_pump_current_pressure(calibration),
        "ro_membrane_a_b": fit_ro_ab(calibration),
    }
    (RESULTS / "calibration_synthetic.json").write_text(
        json.dumps(fits, indent=2), encoding="utf-8"
    )
    public_hardware = ROOT / "web" / "public" / "hardware"
    public_hardware.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "hardware" / "BENCH_RIG.md", public_hardware / "BENCH_RIG.md")
    return {
        "provenance": "SIMULATED",
        "rows": int(len(bench)),
        "adapter_sample": "hardware/samples/bench_like.csv",
        "calibration_sample": "hardware/samples/bench_like_calibration.csv",
        "fit_report": "results/calibration_synthetic.json",
    }


def _write_offline_event_replays(models_by_tier: dict) -> dict:
    """Precompute each supported event so the demo remains interactive offline."""
    from twin.simulator import simulate_unit

    defaults = read_config("scenarios.yaml")["event_defaults"]
    output = {}
    columns = [
        "unit_id",
        "day",
        "scenario",
        "tds_in_mg_l",
        "turbidity_ntu",
        "temp_c",
        "flow_l_h",
        "motor_current_a",
        "pressure_virtual_bar",
        "outlet_tds_mg_l",
        "ro_permeability_est_lmh_bar",
        "raw_resistance_proxy",
        "hydraulic_resistance_index",
        "carbon_exposure_index",
        "daily_litres_mean_l",
        "rul_sediment_d",
        "rul_uf_d",
        "rul_carbon_d",
        "rul_ro_d",
        "pred_p1_sediment_d",
        "pred_p1_uf_d",
        "pred_p1_carbon_d",
        "pred_p1_ro_d",
    ]
    for scenario_idx, scenario in enumerate(SCENARIOS):
        for event_idx, (kind, spec) in enumerate(defaults.items()):
            event = {
                "kind": kind,
                "day": 30,
                "duration_days": int(spec["duration_days"]),
                "value": float(spec["value"]),
            }
            frame = simulate_unit(
                f"OFFLINE-{scenario_idx}-{event_idx}",
                "replay",
                scenario,
                SEED + 10_000 + scenario_idx * 101 + event_idx,
                events=[event],
            )
            frame = add_state_projections(frame)
            for stage in STAGES:
                X = model_features(frame, physics=True, tier="C", stage=stage)
                state = frame[f"ekf_rul_{stage}_C_d"].to_numpy(dtype=float)
                frame[f"pred_p1_{stage}_d"] = np.maximum(
                    0, state + models_by_tier[stage]["C"].predict(X)
                )
            subset = frame[columns].head(220)
            records = []
            for row in subset.to_dict(orient="records"):
                records.append(
                    {
                        key: (value.item() if isinstance(value, np.generic) else value)
                        for key, value in row.items()
                    }
                )
            output[f"{scenario}:{kind}"] = {
                "provenance": "SIMULATED",
                "event": event,
                "readings": records,
            }
    target_dir = ROOT / "web" / "public" / "replays"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "events.json"
    target.write_text(
        json.dumps({"provenance": "SIMULATED", "bundles": output}, separators=(",", ":")),
        encoding="utf-8",
    )
    return {
        "provenance": "SIMULATED",
        "scenarios": len(SCENARIOS),
        "event_types": len(defaults),
        "bundles": len(output),
        "file": "web/public/replays/events.json",
    }


def _write_showcase_replay(
    test: pd.DataFrame, max_units: int = 12, max_days: int = 120
) -> dict[str, object]:
    """Export a compact offline sample for browser and low-bandwidth demo mode."""
    replay_dir = ROOT / "web" / "public" / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    units = list(pd.unique(test["unit_id"]))[:max_units]
    showcase = (
        test.loc[test.unit_id.isin(units)]
        .sort_values(["unit_id", "day"])
        .groupby("unit_id", sort=False)
        .head(max_days)
    )
    cols = [
        "unit_id",
        "day",
        "scenario",
        "tds_in_mg_l",
        "turbidity_ntu",
        "temp_c",
        "flow_l_h",
        "motor_current_a",
        "pressure_virtual_bar",
        "outlet_tds_mg_l",
        "ro_permeability_est_lmh_bar",
        "rul_sediment_d",
        "rul_uf_d",
        "rul_carbon_d",
        "rul_ro_d",
        "raw_resistance_proxy",
        "hydraulic_resistance_index",
        "carbon_exposure_index",
        "daily_litres_mean_l",
        "pred_p1_sediment_d",
        "pred_p1_uf_d",
        "pred_p1_carbon_d",
        "pred_p1_ro_d",
    ]
    bundle = {
        "provenance": "SIMULATED",
        "units": int(showcase.unit_id.nunique()),
        "readings": showcase[cols].to_dict(orient="records"),
    }
    with gzip.open(replay_dir / "showcase.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, separators=(",", ":"))
    (replay_dir / "showcase.json").write_text(
        json.dumps(bundle, separators=(",", ":")), encoding="utf-8"
    )
    return {
        "provenance": "SIMULATED",
        "units": bundle["units"],
        "rows": len(bundle["readings"]),
        "max_days_per_unit": max_days,
        "file": "web/public/replays/showcase.json",
        "compressed_file": "web/public/replays/showcase.json.gz",
    }


def run_pipeline(quick: bool = False, full: bool = False) -> dict:
    """Fit all telemetry tiers, calibrate on validation, then score test and OOD once."""
    start = time.perf_counter()
    RESULTS.mkdir(exist_ok=True)
    model_dir = RESULTS / "models"
    model_dir.mkdir(exist_ok=True)
    cohorts = {
        key: add_state_projections(value)
        for key, value in generate_cohort(quick=quick, full=full, out_dir=DATA).items()
    }
    train, validation, test, ood = (cohorts[key] for key in ("train", "validation", "test", "ood"))
    stages, tiers = STAGES, ("A", "B", "C")
    replacement_fraction = float(
        read_config("model.yaml")["estimator"]["business_replacement_fraction"]
    )
    warning_budget = float(
        read_config("model.yaml")["estimator"][
            "validation_warning_false_alarm_budget_per_unit_year"
        ]
    )

    median_life_volumes = {}
    for stage in stages:
        volumes = []
        for _, unit in train.groupby("unit_id", sort=False):
            life_day = int(unit[f"life_{stage}_d"].iloc[0])
            at_eol = unit.loc[unit.day <= life_day, "cumulative_litres"]
            volumes.append(float(at_eol.iloc[-1]))
        median_life_volumes[stage] = float(np.median(volumes))

    models_by_tier: dict[str, dict[str, Any]] = {stage: {} for stage in stages}
    raw_models: dict[str, Any] = {}
    model_sizes: dict[str, int] = {}
    # Fit all models before any test or OOD evaluation.
    for stage in stages:
        fit = _sample(train, seed=SEED + STAGES.index(stage))
        raw_models[stage] = fit_raw_baseline(train, stage, SEED + 100 + STAGES.index(stage))
        MODELS[stage] = {"b1": raw_models[stage]}
        for tier in tiers:
            state_col = f"ekf_rul_{stage}_{tier}_d"
            X = model_features(fit, physics=True, tier=tier, stage=stage)
            residual = fit[f"rul_{stage}_d"].to_numpy(dtype=float) - fit[state_col].to_numpy(
                dtype=float
            )
            model = make_residual_model(SEED + STAGES.index(stage) * 10 + tiers.index(tier))
            model.fit(X, residual)
            models_by_tier[stage][tier] = model
            MODELS[stage]["p1" if tier == "C" else f"p1_{tier}"] = model
        joblib.dump(MODELS[stage], model_dir / f"{stage}.joblib", compress=3)
        model_sizes[stage] = (model_dir / f"{stage}.joblib").stat().st_size

    q_by_tier: dict[str, dict[str, dict[str, float]]] = {
        tier: {stage: {} for stage in stages} for tier in tiers
    }

    def predict_frame(split: str, include_baselines: bool = False) -> None:
        frame = cohorts[split]
        for stage in stages:
            if include_baselines:
                raw_x = model_features(frame, physics=False, tier="C")
                frame[f"pred_b1_{stage}_d"] = np.maximum(0, raw_models[stage].predict(raw_x))
                frame[f"pred_b0_{stage}_d"] = fixed_schedule_prediction(stage, frame["day"], train)
                recent_use = frame.groupby("unit_id")["litres_dispensed_l"].transform(
                    lambda series: series.rolling(14, min_periods=1).mean()
                )
                frame[f"pred_b0_volume_{stage}_d"] = np.maximum(
                    0,
                    (replacement_fraction * median_life_volumes[stage] - frame.cumulative_litres)
                    / recent_use.clip(lower=1),
                )
            for tier in tiers:
                X = model_features(frame, physics=True, tier=tier, stage=stage)
                state = frame[f"ekf_rul_{stage}_{tier}_d"].to_numpy(dtype=float)
                prediction = np.maximum(0, state + models_by_tier[stage][tier].predict(X))
                frame[f"pred_p1_{tier}_{stage}_d"] = prediction
                if tier == "C":
                    frame[f"pred_p1_{stage}_d"] = prediction

    # Validation is the only split used to fit uncertainty and the warning threshold.
    predict_frame("validation", include_baselines=True)
    for tier in tiers:
        for stage in stages:
            for horizon in HORIZONS:
                rows = _truth_horizon(validation, stage, horizon)
                errors = (rows[f"pred_p1_{tier}_{stage}_d"] - rows[f"rul_{stage}_d"]).to_numpy(
                    dtype=float
                )
                q_by_tier[tier][stage][str(horizon)] = (
                    split_conformal_radius(errors, 0.9) if len(errors) else 0.0
                )

    warning_policy = {}
    warning_events: dict[str, dict[str, Any]] = {"validation": {}, "test": {}, "ood": {}}
    for stage in stages:
        sigma = float(np.std(validation[f"pred_p1_{stage}_d"] - validation[f"rul_{stage}_d"]))
        best = {"tau": 0.5, "false_alarms_per_unit_year": math.inf, "recall": -1.0}
        for tau in np.linspace(0.1, 0.95, 18):
            events = _first_warning_events(
                validation, stage, f"pred_p1_{stage}_d", float(tau), sigma
            )
            summary = _warning_summary(validation, stage, events)
            recall = 1 - summary["missed_failure_fraction"]
            if summary["false_alarms_per_unit_year"] <= warning_budget and recall > best["recall"]:
                best = {
                    "tau": float(tau),
                    "false_alarms_per_unit_year": summary["false_alarms_per_unit_year"],
                    "recall": recall,
                }
        warning_policy[stage] = best
        warning_policy[stage]["validation_residual_sigma_days"] = sigma
        validation_events = _first_warning_events(
            validation, stage, f"pred_p1_{stage}_d", best["tau"], sigma
        )
        warning_events["validation"][stage] = _warning_summary(validation, stage, validation_events)

    # Models and policies are frozen. Test and OOD are now each scored one time.
    predict_frame("test", include_baselines=True)
    predict_frame("ood", include_baselines=True)
    for stage in stages:
        sigma = float(np.std(validation[f"pred_p1_{stage}_d"] - validation[f"rul_{stage}_d"]))
        for split in ("test", "ood"):
            frame = cohorts[split]
            events = _first_warning_events(
                frame, stage, f"pred_p1_{stage}_d", warning_policy[stage]["tau"], sigma
            )
            warning_events[split][stage] = _warning_summary(frame, stage, events)
    inference_ms = {}
    for stage in stages:
        sample = model_features(test, physics=True, tier="C", stage=stage).iloc[
            : min(5000, len(test))
        ]
        tick = time.perf_counter()
        for _ in range(5):
            models_by_tier[stage]["C"].predict(sample)
        inference_ms[stage] = (time.perf_counter() - tick) * 1000 / max(5 * len(sample), 1)

    split_check = (
        set(train.unit_id).isdisjoint(validation.unit_id)
        and set(train.unit_id).isdisjoint(test.unit_id)
        and set(train.unit_id).isdisjoint(ood.unit_id)
        and set(validation.unit_id).isdisjoint(test.unit_id)
        and set(validation.unit_id).isdisjoint(ood.unit_id)
        and set(test.unit_id).isdisjoint(ood.unit_id)
    )
    metrics: dict = {
        "provenance": "SIMULATED",
        "generated_at": "deterministic seed 20261101; timestamps intentionally omitted",
        "seed": SEED,
        "cohort_units": {k: int(v.unit_id.nunique()) for k, v in cohorts.items()},
        "cohort_rows": {k: int(len(v)) for k, v in cohorts.items()},
        "grouped_split_check": bool(split_check),
        "horizons_days": list(HORIZONS),
        "targets_are_proposals_not_acceptance_claims": True,
        "stages": {},
        "warning_policy": warning_policy,
        "warning_false_alarm_budget_per_unit_year": warning_budget,
        "warning_metrics": warning_events,
        "conformal_nominal_coverage": 0.9,
        "model_size_bytes_by_stage": model_sizes,
        "inference_latency_ms_per_row_by_stage": inference_ms,
    }
    for stage in stages:
        stage_metrics: dict[str, Any] = {}
        for split in ("test", "ood"):
            frame = cohorts[split]
            stage_metrics[split] = {
                "p1": _horizon_stats(frame, stage, f"pred_p1_{stage}_d", q_by_tier["C"][stage]),
                "b1": _horizon_stats(frame, stage, f"pred_b1_{stage}_d"),
                "b0_schedule": _horizon_stats(frame, stage, f"pred_b0_{stage}_d"),
                "b0_volume": _horizon_stats(frame, stage, f"pred_b0_volume_{stage}_d"),
            }
        stage_metrics["conformal_q_days_by_horizon"] = q_by_tier["C"][stage]
        stage_metrics["warning"] = {key: warning_events[key][stage] for key in warning_events}
        metrics["stages"][stage] = stage_metrics
    metrics["telemetry_tiers"] = {
        tier: {
            "features": TIER_RAW[tier] + TIER_PHYS[tier] + ["ekf_state_rul"],
            "n_features": len(TIER_RAW[tier] + TIER_PHYS[tier]) + 1,
            "provenance": "SIMULATED",
            "test": {
                stage: _horizon_stats(
                    test, stage, f"pred_p1_{tier}_{stage}_d", q_by_tier[tier][stage]
                )
                for stage in stages
            },
            "ood": {
                stage: _horizon_stats(
                    ood, stage, f"pred_p1_{tier}_{stage}_d", q_by_tier[tier][stage]
                )
                for stage in stages
            },
            "conformal_q_days_by_stage": q_by_tier[tier],
        }
        for tier in tiers
    }
    metrics["signature_matrix"] = _signature_matrix()
    metrics["business_impact"] = _business_impact(
        test, {stage: test[f"pred_p1_{stage}_d"].to_numpy() for stage in stages}, warning_policy
    )
    metrics["offline_event_replays"] = _write_offline_event_replays(models_by_tier)
    checks = {
        "NASA_CMAPSS": {
            "status": "NOT AVAILABLE IN THIS RUN",
            "reason": "No compatible NASA benchmark file was obtained; see the fetch probe.",
        },
        "RO_fouling": {
            "status": "NOT AVAILABLE IN THIS RUN",
            "reason": "No raw, licensed, compatible run-to-failure time-series obtained.",
        },
        "CGWB": {
            "status": "METADATA FOUND; VALUES NOT INGESTED",
            "reason": "Metadata is not compatible run-to-failure evidence; no values were imported.",
        },
    }
    fetch_path = RESULTS / "public_fetch.json"
    if fetch_path.exists():
        checks["fetch_probe"] = json.loads(fetch_path.read_text(encoding="utf-8"))
    metrics["public_data_checks"] = checks
    metrics["compute"] = {"pipeline_wall_seconds": time.perf_counter() - start, "device": "CPU"}
    metrics["provenance_legend"] = {
        "SIMULATED": "Generated by this deterministic twin",
        "PUBLIC DATA": "External dataset actually ingested",
        "BENCH": "Not yet collected",
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    for split in ("validation", "test", "ood"):
        cohorts[split].to_parquet(RESULTS / f"{split}_predictions.parquet", index=False)
    metrics["hardware_samples"] = _write_generated_bench_samples(test)
    metrics["offline_showcase"] = _write_showcase_replay(test)
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    from twin.physics import (
        cake_pressure_drop_pa,
        current_from_pressure_a,
        normalized_permeability_lmh_bar,
        osmotic_pressure_bar,
        permeate_flow_l_h,
        ro_flux_lmh,
        salt_balance,
        temperature_factor,
        virtual_pressure_bar,
        water_viscosity_pa_s,
    )

    physics = read_config("physics.yaml")
    ro_cfg, pump_cfg = physics["ro"], physics["pump"]
    area = float(ro_cfg["area_m2"]["value"])
    a0 = float(ro_cfg["permeability_lmh_bar"]["value"])
    pressure_ref = float(ro_cfg["nominal_pressure_bar"]["value"])
    tds_ref = float(physics["calibration_sweep"]["feed_tds_mg_l"]["value"])
    tds_high = 3 * tds_ref
    permeate_pressure = float(ro_cfg["permeate_backpressure_bar"]["value"])
    flux_args = (
        float(ro_cfg["cp_factor"]["value"]),
        float(ro_cfg["osmotic_bar_per_g_l"]["value"]),
        float(ro_cfg["temp_coefficient_per_c"]["value"]),
    )
    healthy_600 = ro_flux_lmh(a0, pressure_ref, tds_ref, 25.0, permeate_pressure, *flux_args)
    healthy_1800 = ro_flux_lmh(a0, pressure_ref, tds_high, 25.0, permeate_pressure, *flux_args)
    fouled_600 = ro_flux_lmh(
        a0 * float(ro_cfg["golden_fouled_permeability_fraction"]["value"]),
        pressure_ref,
        tds_ref,
        25.0,
        permeate_pressure,
        *flux_args,
    )
    current_ref = current_from_pressure_a(
        pressure_ref,
        float(pump_cfg["current_intercept_a"]["value"]),
        float(pump_cfg["current_slope_a_bar"]["value"]),
    )
    darcy = physics["darcy_golden"]
    darcy_flow = float(darcy["flow_l_min"]["value"]) / 1000 / 60
    clean_dp = cake_pressure_drop_pa(
        darcy_flow,
        float(darcy["area_m2"]["value"]),
        float(darcy["viscosity_pa_s"]["value"]),
        float(darcy["clean_resistance_per_m"]["value"]),
    )
    caked_dp = cake_pressure_drop_pa(
        darcy_flow,
        float(darcy["area_m2"]["value"]),
        float(darcy["viscosity_pa_s"]["value"]),
        float(darcy["caked_resistance_per_m"]["value"]),
    )
    salt = physics["salt_balance_golden"]
    reject_flow, reject_concentration_factor = salt_balance(
        float(salt["feed_l_h"]["value"]),
        float(salt["permeate_l_h"]["value"]),
        float(salt["recovery_fraction"]["value"]),
    )
    tds_grid, temp_grid = np.linspace(100, 2500, 20), np.linspace(10, 35, 8)
    invariant_errors = [
        abs(
            normalized_permeability_lmh_bar(
                ro_flux_lmh(
                    a0, pressure_ref, float(tds), float(temp), permeate_pressure, *flux_args
                ),
                pressure_ref,
                float(tds),
                float(temp),
                permeate_pressure,
                *flux_args,
            )
            / a0
            - 1
        )
        for tds in tds_grid
        for temp in temp_grid
    ]
    golden = {
        "provenance": "SIMULATED",
        "G1": {
            "healthy_600": {
                "osmotic_pressure_bar": osmotic_pressure_bar(tds_ref, *flux_args[:2]),
                "ndp_bar": pressure_ref
                - permeate_pressure
                - osmotic_pressure_bar(tds_ref, *flux_args[:2]),
                "flux_lmh": healthy_600,
                "permeate_l_h": permeate_flow_l_h(healthy_600, area),
                "normalized_health": normalized_permeability_lmh_bar(
                    healthy_600, pressure_ref, tds_ref, 25.0, permeate_pressure, *flux_args
                )
                / a0,
            },
            "healthy_1800": {
                "osmotic_pressure_bar": osmotic_pressure_bar(tds_high, *flux_args[:2]),
                "ndp_bar": pressure_ref
                - permeate_pressure
                - osmotic_pressure_bar(tds_high, *flux_args[:2]),
                "flux_lmh": healthy_1800,
                "permeate_l_h": permeate_flow_l_h(healthy_1800, area),
                "raw_flow_ratio_vs_600": healthy_1800 / healthy_600,
                "normalized_health": normalized_permeability_lmh_bar(
                    healthy_1800, pressure_ref, tds_high, 25.0, permeate_pressure, *flux_args
                )
                / a0,
            },
            "fouled_600": {
                "flux_lmh": fouled_600,
                "permeate_l_h": permeate_flow_l_h(fouled_600, area),
                "normalized_health": normalized_permeability_lmh_bar(
                    fouled_600, pressure_ref, tds_ref, 25.0, permeate_pressure, *flux_args
                )
                / a0,
            },
        },
        "G2": {
            "viscosity_25_pa_s": water_viscosity_pa_s(25.0),
            "viscosity_15_pa_s": water_viscosity_pa_s(
                float(physics["calibration_sweep"]["cold_comparison_temperature_c"]["value"])
            ),
            "temperature_factor_15_vs_25": temperature_factor(
                float(physics["calibration_sweep"]["cold_comparison_temperature_c"]["value"]),
                float(ro_cfg["temp_coefficient_per_c"]["value"]),
            ),
        },
        "G3": {
            "current_at_4_5_bar_a": current_ref,
            "pressure_recovered_bar": virtual_pressure_bar(
                current_ref,
                float(pump_cfg["current_intercept_a"]["value"]),
                float(pump_cfg["current_slope_a_bar"]["value"]),
            ),
        },
        "G4": {
            "clean_pressure_drop_pa": clean_dp,
            "caked_pressure_drop_pa": caked_dp,
            "caked_pressure_drop_bar": caked_dp / 100000,
        },
        "G5": {
            "feed_l_h": float(salt["feed_l_h"]["value"]),
            "permeate_l_h": float(salt["permeate_l_h"]["value"]),
            "reject_l_h": reject_flow,
            "mass_balance_error_l_h": float(salt["feed_l_h"]["value"])
            - float(salt["permeate_l_h"]["value"])
            - reject_flow,
            "reject_concentration_factor": reject_concentration_factor,
            "max_abs_normalized_health_error_fraction": max(invariant_errors),
        },
        "model_note": "Golden outputs are generated from the checked physics functions at pipeline time.",
    }
    (RESULTS / "physics_golden.json").write_text(json.dumps(golden, indent=2), encoding="utf-8")
    public_evidence = ROOT / "web" / "public" / "evidence"
    public_evidence.mkdir(parents=True, exist_ok=True)
    for name, value in (("metrics.json", metrics), ("physics_golden.json", golden)):
        (public_evidence / name).write_text(
            json.dumps(value, separators=(",", ":")), encoding="utf-8"
        )
    (RESULTS / "schema.json").write_text(
        json.dumps(
            {
                "columns": list(test.columns),
                "units": {
                    "flow_l_h": "L/h",
                    "tds_in_mg_l": "mg/L",
                    "temp_c": "degC",
                    "pressure_virtual_bar": "bar",
                    "rul_*_d": "days",
                    "rul_*_l": "litres",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (public_evidence / "scenarios.json").write_text(
        json.dumps(
            [{"id": name, **values} for name, values in SCENARIOS.items()], separators=(",", ":")
        ),
        encoding="utf-8",
    )
    _write_generated_docs(metrics)
    from scripts.render_figures import render

    render(metrics)
    return metrics


def _write_generated_docs(metrics: dict) -> None:
    doc = [
        "# Evaluation (generated)",
        "",
        "All scores are SIMULATED and regenerated from `results/metrics.json`. The model and warning policy were fitted/calibrated on TRAIN/VALIDATION before each held-out TEST and OOD split was scored. These are not field-validation results.",
        "",
    ]
    for stage, values in metrics["stages"].items():
        doc.extend(
            [
                f"## {stage.title()}",
                "",
                "| Split | Model | Horizon (days) | MAE (days) | MAE (L) | Relative error | NASA score | 90% interval coverage |",
                "|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for split in ("test", "ood"):
            for model in ("p1", "b1", "b0_schedule", "b0_volume"):
                for horizon, stats in values[split][model].items():
                    coverage = stats.get("coverage", "—")
                    doc.append(
                        f"| {split.upper()} SIMULATED | {model} | {horizon} | {stats['mae_days']:.2f} | {stats['mae_litres']:.2f} | {stats['mean_absolute_relative_error']:.3f} | {stats['nasa_score']:.3f} | {coverage if isinstance(coverage, str) else f'{coverage:.3f}'} |"
                    )
        doc.append("")
    doc.extend(
        [
            "## Telemetry tiers",
            "",
            "| Tier | Split | Stage | Horizon (days) | MAE (days) | Relative error | 90% interval coverage |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for tier, tier_values in metrics["telemetry_tiers"].items():
        for split in ("test", "ood"):
            for stage, horizons in tier_values[split].items():
                for horizon, stats in horizons.items():
                    coverage = stats.get("coverage", "—")
                    rendered_coverage = coverage if isinstance(coverage, str) else f"{coverage:.3f}"
                    doc.append(
                        f"| {tier} | {split.upper()} SIMULATED | {stage} | {horizon} | {stats['mae_days']:.2f} | {stats['mean_absolute_relative_error']:.3f} | {rendered_coverage} |"
                    )
    doc.extend(
        [
            "",
            "## Warning policy",
            "",
            f"Validation false-alarm budget: {metrics['warning_false_alarm_budget_per_unit_year']:.3f} per unit-year.",
            "",
            "| Stage | Validation threshold | Validation recall | Test false alarms / unit-year | Test missed fraction | OOD false alarms / unit-year | OOD missed fraction |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for stage, policy in metrics["warning_policy"].items():
        test_warning = metrics["warning_metrics"]["test"][stage]
        ood_warning = metrics["warning_metrics"]["ood"][stage]
        doc.append(
            f"| {stage} | {policy['tau']:.3f} | {policy['recall']:.3f} | {test_warning['false_alarms_per_unit_year']:.3f} | {test_warning['missed_failure_fraction']:.3f} | {ood_warning['false_alarms_per_unit_year']:.3f} | {ood_warning['missed_failure_fraction']:.3f} |"
        )
    doc.extend(
        [
            "",
            "## Fleet policy simulation",
            "",
            f"Horizon: {metrics['business_impact']['assumptions']['horizon_years']} simulated years; {metrics['business_impact']['assumptions']['households']} simulated households.",
            "",
            "| Policy | Useful life wasted | Failing before replacement | Failures per 1,000 households | Replacements per 1,000 households |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for policy, values in metrics["business_impact"]["policies"].items():
        doc.append(
            f"| {policy} | {values['mean_useful_life_wasted_fraction']:.3f} | {values['cartridges_failing_before_replacement_fraction']:.3f} | {values['cartridge_failures_per_1000_households_3y']} | {values['replacements_per_1000_households_3y']} |"
        )
    doc.extend(
        [
            "",
            "## Runtime and artifact size",
            "",
            "| Stage | Joblib bundle (bytes) | Inference (ms / row) |",
            "|---|---:|---:|",
        ]
    )
    for stage, size in metrics["model_size_bytes_by_stage"].items():
        doc.append(
            f"| {stage} | {size} | {metrics['inference_latency_ms_per_row_by_stage'][stage]:.6f} |"
        )
    doc.extend(
        [
            "",
            "## Data and compute",
            "",
            f"Grouped unit split check: `{metrics['grouped_split_check']}`.",
            f"Pipeline wall time: {metrics['compute']['pipeline_wall_seconds']:.2f} seconds (CPU).",
            f"Offline event bundles: {metrics['offline_event_replays']['bundles']}.",
            f"Synthetic bench adapter sample rows: {metrics['hardware_samples']['rows']}.",
            "",
            "Public-data checks are recorded in `results/public_fetch.json`; no external dataset or physical bench measurement was ingested. Model results, the policy simulation, signature matrix, and calibration fixture are SIMULATED. No real-world validation or drinking-water safety claim is made.",
        ]
    )
    (ROOT / "docs" / "EVALUATION.md").write_text("\n".join(doc) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text(_readme(metrics), encoding="utf-8")


def _readme(metrics: dict) -> str:
    return f"""# FilterTwin

**Predictive maintenance concept for household RO purifiers.** Every model metric below is generated from a synthetic digital twin, not from a purifier fleet. UI title: **Atomberg Home (concept UI)**. No Atomberg marks or proprietary hardware assumptions are used.

## Quickstart

1. `make setup` (creates the environment, installs dependencies, and runs the quick pipeline)
2. `make demo` (starts FastAPI and Vite in Demo-Safe-capable mode)

On Windows without GNU Make: run `scripts\\setup.ps1`, then `scripts\\demo.ps1`. To regenerate the full cohorts between setup and demo, run `make reproduce`.

For a short deterministic run: `make quick`. For the requested full cohort and regenerated evidence: `make reproduce` (or `make full`).

## Current generated run

- Units: {json.dumps(metrics["cohort_units"], sort_keys=True)}
- Rows: {json.dumps(metrics["cohort_rows"], sort_keys=True)}
- Grouped split check: {metrics["grouped_split_check"]}
- Pipeline wall time: {metrics["compute"]["pipeline_wall_seconds"]:.2f}s on CPU
- Provenance: SIMULATED. External validation and bench data are pending.

## What it demonstrates

- Solution-diffusion RO normalization for pressure, osmotic pressure, and temperature.
- Virtual pump pressure from a configurable current-pressure line.
- Cake filtration and a Thomas-style carbon breakthrough proxy with RO oxidation coupling.
- A small health-state Kalman filter plus gradient-boosted residual correction, baselines, validation conformal calibration, and one-time held-out OOD reporting.
- FastAPI telemetry/evidence/ingest endpoints and an offline replay bundle.
- A bench-rig proposal and adapter path.

## Routes

`/twin`, `/why`, `/app`, `/fleet`, `/evidence`, `/hardware`, `/about`, `/demo`.

## Run evidence

See [docs/EVALUATION.md](docs/EVALUATION.md), [docs/MODEL_CARD.md](docs/MODEL_CARD.md), [docs/CLAIMS_REGISTER.md](docs/CLAIMS_REGISTER.md), and [FINAL_REPORT.md](FINAL_REPORT.md). Charts and app claims carry SIMULATED/PUBLIC DATA/BENCH provenance.

Playwright desktop and phone captures are written to `docs/screenshots/` when the browser gate runs. Vector figures for slides are in `docs/figures/`.

## Architecture

```mermaid
flowchart LR
  C[configs/*.yaml] --> T[Pure Python twin]
  T --> D[Parquet grouped cohorts]
  D --> M[EKF + boosted residual / baselines]
  M --> R[results/*.json + replay bundle]
  R --> A[FastAPI] --> W[Offline React UI]
  H[Bench CSV adapter] --> D
```
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    result = run_pipeline(quick=args.quick, full=args.full)
    print(
        json.dumps(
            {
                "cohort_units": result["cohort_units"],
                "cohort_rows": result["cohort_rows"],
                "grouped_split_check": result["grouped_split_check"],
                "wall_seconds": result["compute"]["pipeline_wall_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
