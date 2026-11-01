"""Deterministic daily-resolution household and purifier twin."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from twin.physics import (
    cake_pressure_drop_pa,
    current_from_pressure_a,
    normalized_permeability_lmh_bar,
    osmotic_pressure_bar,
    solve_operating_pressure_bar,
    temperature_factor,
    thomas_breakthrough_fraction,
    virtual_pressure_bar,
)

ROOT = Path(__file__).resolve().parents[1]


def read_config(filename: str) -> dict:
    with (ROOT / "configs" / filename).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


SCENARIO_CONFIG = read_config("scenarios.yaml")
SCENARIOS = SCENARIO_CONFIG["scenarios"]
PHYS = read_config("physics.yaml")
THRESHOLD_CONFIG = read_config("thresholds.yaml")
THRESHOLDS = THRESHOLD_CONFIG["end_of_life"]
SENSORS = read_config("sensors.yaml")["simulation_noise"]
SEED = int(read_config("model.yaml")["seed"])
SIM = PHYS["simulation"]
PUMP = PHYS["pump"]
FILTERS = PHYS["filters"]
RO_DECAY = PHYS["ro_degradation"]

STAGES = ("sediment", "uf", "carbon", "ro", "uv", "alkaliser")
LIFE_FEATURES = ["rul_sediment_d", "rul_uf_d", "rul_carbon_d", "rul_ro_d"]
FEATURES_RAW = [
    "outlet_tds_mg_l",
    "pump_runtime_h",
    "litres_dispensed_l",
    "motor_current_a",
    "rpm",
    "tds_in_mg_l",
    "flow_l_h",
    "temp_c",
    "turbidity_ntu",
    "day",
]
FEATURES_PHYS = FEATURES_RAW + [
    "pressure_virtual_bar",
    "osmotic_pressure_bar",
    "ro_permeability_est_lmh_bar",
    "raw_resistance_proxy",
    "carbon_exposure_index",
    "ro_rejection_fraction",
    "hydraulic_resistance_index",
]


def _life_days(rng: np.random.Generator, scenario: dict, name: str) -> int:
    """Sample stage life with unit variation and scenario stress (all simulator assumptions)."""
    scale = float(THRESHOLD_CONFIG["nominal_life_days"][name]["value"])
    reference_turbidity = float(SIM["reference_turbidity_ntu"]["value"])
    reference_chlorine = float(SIM["reference_chlorine_mg_l"]["value"])
    reference_ro_stress = float(SIM["reference_ro_stress"]["value"])
    if name == "sediment":
        scale *= math.sqrt(reference_turbidity / max(scenario["turbidity_ntu"], 1))
    elif name == "uf":
        scale *= math.sqrt(reference_turbidity / max(scenario["turbidity_ntu"], 1))
    elif name == "carbon":
        scale *= reference_chlorine / max(scenario["chlorine_mg_l"], 0.05)
    elif name == "ro":
        scale *= math.sqrt(
            reference_ro_stress / max(scenario["hardness"] * scenario["tds_mg_l"] / 1000, 0.1)
        )
    elif name == "alkaliser":
        scale *= 5 / 3.0
    varied = scale * rng.lognormal(mean=0.0, sigma=float(SIM["life_lognormal_sigma"]["value"]))
    return int(
        np.clip(varied, float(SIM["life_days_min"]["value"]), float(SIM["life_days_max"]["value"]))
    )


def simulate_unit(
    unit_id: str,
    split: str,
    scenario_name: str,
    seed: int,
    ood: bool = False,
    events: list[dict] | None = None,
) -> pd.DataFrame:
    """Simulate one purifier through the latest stage end-of-life.

    Every sensor reading has deterministic noise for the provided per-unit seed.
    The latent states remain in the output so test errors can be audited.
    """
    rng = np.random.default_rng(seed)
    water = dict(SCENARIOS[scenario_name])
    household = int(
        rng.integers(int(SIM["household_min"]["value"]), int(SIM["household_max"]["value"]) + 1)
    )
    stage_life = {s: _life_days(rng, water, s) for s in STAGES}
    n_days = int(math.ceil(max(stage_life.values()) * 1.35)) + 1
    data = []
    cumulative_l = 0.0
    cumulative_chlorine = 0.0
    daily_litres_mean = household * float(SIM["litres_per_person_day"]["value"])
    chlorine_load_eol = daily_litres_mean * water["chlorine_mg_l"] * stage_life["carbon"]
    chlorine_capacity = chlorine_load_eol / 0.90

    # OOD perturbations are never used by the training cohort.
    current_bias = rng.normal(0.0, float(SENSORS["current_bias_sigma_a"]["value"])) if ood else 0.0
    current_drift = (
        rng.normal(
            float(SENSORS["current_drift_mean_a_per_day"]["value"]),
            float(SENSORS["current_drift_sigma_a_per_day"]["value"]),
        )
        if ood
        else 0.0
    )
    flow_scale = rng.uniform(*SIM["ood_flow_scale"]["value"]) if ood else 1.0
    inlet_bar = rng.uniform(*SIM["ood_inlet_pressure_bar"]["value"]) if ood else 1.2
    pump_wear = rng.uniform(*SIM["ood_pump_wear_fraction"]["value"]) if ood else 0.0
    fault = rng.choice(
        ["pump_wear", "air_ingress", "voltage_sag", "sensor_drift", "partial_replacement"]
    )
    if ood and fault == "pump_wear":
        pump_wear += float(SIM["ood_pump_wear_extra_fraction"]["value"])
    event_list = events or []
    event_defaults = read_config("scenarios.yaml")["event_defaults"]
    for event in event_list:
        if event.get("kind") not in event_defaults:
            raise ValueError(f"unsupported event kind: {event.get('kind')}")
    silt_shock = 0.0
    pump_wear_shock = 0.0

    for day in range(n_days):
        # Slow seasonal variation and discrete water events.
        season = math.sin(2 * math.pi * day / float(SIM["season_period_days"]["value"]))
        temp_c = (
            water["temp_c"]
            + float(SIM["seasonal_temperature_amplitude_c"]["value"]) * season
            + rng.normal(0, float(SIM["temperature_noise_sigma_c"]["value"]))
        )
        tds = water["tds_mg_l"] * (
            1 + float(SIM["seasonal_tds_amplitude_fraction"]["value"]) * season
        ) + rng.normal(0, float(SIM["tds_noise_sigma_mg_l"]["value"]))
        turbidity = max(
            0.2,
            water["turbidity_ntu"]
            * (1 + float(SIM["turbidity_seasonal_amplitude_fraction"]["value"]) * max(season, 0))
            + rng.normal(0, float(SIM["turbidity_noise_sigma_ntu"]["value"])),
        )
        chlorine = max(
            0.01,
            water["chlorine_mg_l"]
            * (1 + rng.normal(0, float(SIM["chlorine_measurement_noise_fraction"]["value"]))),
        )
        active_events = [
            e
            for e in event_list
            if int(e.get("day", 0)) <= day < int(e.get("day", 0)) + int(e.get("duration_days", 1))
        ]
        event_pump_wear = pump_wear + pump_wear_shock
        event_usage_multiplier = 1.0
        for event in active_events:
            kind = event["kind"]
            value = float(event.get("value", event_defaults[kind]["value"]))
            if kind == "silt_spike":
                turbidity = value
                silt_shock += float(FILTERS["sediment_shock_health_loss_per_day"]["value"])
            elif kind == "tanker_tds_switch":
                tds = value
            elif kind == "chlorine_breakthrough":
                chlorine = value
            elif kind == "cold_snap":
                temp_c = value
            elif kind == "pump_wear":
                if day == int(event.get("day", 0)):
                    pump_wear_shock += value
                event_pump_wear = min(0.8, pump_wear + pump_wear_shock)
            elif kind == "usage_change":
                event_usage_multiplier = value
        if scenario_name == "monsoon_silt" and day % 97 in range(10, 18):
            bounds = SCENARIO_CONFIG["seasonal_events"]["monsoon_silt"]
            turbidity = float(rng.uniform(bounds["turbidity_min_ntu"], bounds["turbidity_max_ntu"]))
        if scenario_name == "tanker_switching" and day > stage_life["sediment"] * 0.35:
            defaults = SCENARIO_CONFIG["seasonal_events"]["tanker_switching"]
            tds *= defaults["tds_multiplier"]
            turbidity = max(turbidity, defaults["minimum_turbidity_ntu"])
        if scenario_name == "hard_water_scaling" and day % 120 in range(0, 8):
            bounds = SCENARIO_CONFIG["seasonal_events"]["hard_water_scaling"]
            tds = float(rng.uniform(bounds["tds_min_mg_l"], bounds["tds_max_mg_l"]))
        if scenario_name == "irregular_usage" and day % 35 in range(20, 25):
            demand = float(SIM["holiday_demand_multiplier"]["value"]) * daily_litres_mean
        else:
            day_factor = (
                float(SIM["weekend_demand_multiplier"]["value"]) if day % 7 in (5, 6) else 1.0
            )
            demand = (
                daily_litres_mean
                * day_factor
                * rng.lognormal(0, float(SIM["daily_demand_log_sigma"]["value"]))
                * event_usage_multiplier
            )
        if rng.random() < float(SIM["holiday_probability_per_day"]["value"]):
            demand *= float(SIM["holiday_demand_multiplier"]["value"])
        cumulative_l += demand
        cumulative_chlorine += demand * chlorine

        fractions = {s: min(day / max(stage_life[s], 1), 1.25) for s in STAGES}
        sediment_health = max(
            float(SIM["sediment_health_floor"]["value"]),
            1
            - float(FILTERS["eol_cake_health_loss"]["value"]) * fractions["sediment"]
            - silt_shock,
        )
        uf_health = max(
            float(SIM["uf_health_floor"]["value"]),
            1 - float(FILTERS["eol_cake_health_loss"]["value"]) * fractions["uf"],
        )
        carbon_load_fraction = cumulative_chlorine / max(chlorine_capacity, 1e-9)
        carbon_bt = thomas_breakthrough_fraction(
            carbon_load_fraction, 1.0, PHYS["carbon"]["logistic_steepness_per_capacity"]["value"]
        )
        ro_fouling = min(
            float(RO_DECAY["maximum_fouling_loss_fraction"]["value"]),
            float(RO_DECAY["fouling_loss_at_reference"]["value"]) * fractions["ro"]
            + float(RO_DECAY["turbidity_fouling_multiplier"]["value"])
            * (turbidity / max(water["turbidity_ntu"], 1) - 1),
        )
        scaling = (
            float(RO_DECAY["scaling_loss_multiplier"]["value"])
            * fractions["ro"]
            * water["hardness"]
            * tds
            / 1000
        )
        ro_a = max(
            float(RO_DECAY["minimum_permeability_lmh_bar"]["value"]),
            PHYS["ro"]["permeability_lmh_bar"]["value"] * (1 - ro_fouling - scaling),
        )
        oxidation = max(0.0, cumulative_chlorine / max(chlorine_capacity, 1e-9))
        ro_b = PHYS["ro"]["salt_passage_lmh"]["value"] * (
            1 + float(RO_DECAY["oxidation_salt_passage_multiplier"]["value"]) * oxidation
        )
        if ood and fault == "partial_replacement" and day == int(stage_life["ro"] * 0.55):
            sediment_health = min(1.0, sediment_health + 0.22)
            uf_health = min(1.0, uf_health + 0.18)

        viscosity_factor = temperature_factor(temp_c, PHYS["ro"]["temp_coefficient_per_c"]["value"])
        # Darcy resistance grows with cake loading; a flush recovers only the reversible fraction.
        sediment_r = float(FILTERS["sediment_reference_resistance_per_m"]["value"]) * (
            1
            + float(FILTERS["sediment_cake_multiplier_at_reference"]["value"])
            * (1 - sediment_health)
        )
        uf_r = float(FILTERS["uf_reference_resistance_per_m"]["value"]) * (
            1 + float(FILTERS["uf_cake_multiplier_at_reference"]["value"]) * (1 - uf_health)
        )
        base_flow_m3_s = max(demand / float(PUMP["daily_hours"]["value"]), 0.5) / 1000 / 60
        mu = float(PHYS["filtration"]["viscosity_pa_s_25c"]["value"]) / viscosity_factor
        sediment_dp_pa = cake_pressure_drop_pa(
            base_flow_m3_s, float(FILTERS["sediment_area_m2"]["value"]), mu, sediment_r
        )
        uf_dp_pa = cake_pressure_drop_pa(
            base_flow_m3_s, float(FILTERS["uf_area_m2"]["value"]), mu, uf_r
        ) * float(FILTERS["uf_relative_pressure_factor"]["value"])
        total_dp_bar = (sediment_dp_pa + uf_dp_pa) / 100000
        suction_bar = inlet_bar - total_dp_bar
        starvation = float(
            np.clip(
                (suction_bar - float(PUMP["suction_cutoff_bar"]["value"]))
                / float(PUMP["starvation_recovery_span_bar"]["value"]),
                float(PUMP["minimum_starvation_flow_fraction"]["value"]),
                1.0,
            )
        )
        rpm_model = float(PUMP["rpm"]["value"]) * (
            1 - event_pump_wear * float(PUMP["rpm_wear_fraction"]["value"])
        )
        pump_capacity = (
            PHYS["ro"]["pump_area_l_h"]["value"]
            * (rpm_model / float(PUMP["rpm"]["value"]))
            * starvation
            * (1 - event_pump_wear)
        )
        pressure, perm_l_h, reject_l_h = solve_operating_pressure_bar(
            pump_capacity_l_h=pump_capacity,
            pump_slip_per_bar=PHYS["ro"]["pump_slip_per_bar"]["value"],
            reject_coefficient_l_h_sqrt_bar=PHYS["ro"]["reject_coefficient_l_h_sqrt_bar"]["value"],
            permeability_lmh_bar=ro_a,
            area_m2=PHYS["ro"]["area_m2"]["value"],
            tds_mg_l=tds,
            temp_c=temp_c,
            permeate_pressure_bar=PHYS["ro"]["permeate_backpressure_bar"]["value"],
            cp_factor=PHYS["ro"]["cp_factor"]["value"],
            osmotic_bar_per_g_l=PHYS["ro"]["osmotic_bar_per_g_l"]["value"],
            temp_coefficient=PHYS["ro"]["temp_coefficient_per_c"]["value"],
            max_pressure_bar=PHYS["ro"]["max_operating_pressure_bar"]["value"],
        )
        production_flow = max(0.1, perm_l_h * flow_scale)
        pump_runtime = min(
            float(PUMP["max_runtime_hours_per_day"]["value"]), demand / production_flow
        )
        fill_time = min(float(PUMP["max_fill_time_h"]["value"]), demand / max(production_flow, 0.1))
        feed_flow = perm_l_h + reject_l_h
        recovery = perm_l_h / max(feed_flow, 1e-6)
        flux = perm_l_h / PHYS["ro"]["area_m2"]["value"]
        rejection = 1 - ro_b / max(ro_a * max(flux, 0.01) + ro_b, 1e-6)
        outlet_tds = max(0.0, tds * (1 - rejection))
        current_intercept = float(PHYS["pump"]["current_intercept_a"]["value"])
        current_slope = float(PHYS["pump"]["current_slope_a_bar"]["value"])
        motor_current = (
            current_from_pressure_a(pressure, current_intercept, current_slope)
            + current_bias
            + day * current_drift
            + event_pump_wear * float(PUMP["current_wear_increment_a"]["value"])
        )
        if (
            ood
            and fault == "voltage_sag"
            and day > float(SIM["event_outlier_day_fraction"]["value"]) * n_days
        ):
            motor_current *= float(SIM["voltage_sag_fraction"]["value"])
        ripple = (
            float(SIM["ro_base_ripple_a"]["value"])
            + (1 - starvation) * float(SIM["ripple_starvation_gain_a"]["value"])
            + event_pump_wear * float(SIM["ripple_wear_gain_a"]["value"])
            + abs(rng.normal(0, float(SENSORS["ripple_noise_sigma_a"]["value"])))
        )
        if (
            ood
            and fault == "air_ingress"
            and day > float(SIM["air_ingress_start_fraction"]["value"]) * n_days
        ):
            ripple += float(SIM["air_ingress_current_ripple_a"]["value"])
            production_flow *= float(SIM["air_ingress_flow_fraction"]["value"])
        current_measured = motor_current + rng.normal(
            0, float(SENSORS["current_measurement_sigma_a"]["value"])
        )
        flow_measured = max(
            0.0, production_flow * rng.normal(1, float(SENSORS["flow_relative_sigma"]["value"]))
        )
        pressure_virtual = virtual_pressure_bar(current_measured, current_intercept, current_slope)
        flow_lmh_observed = flow_measured / PHYS["ro"]["area_m2"]["value"]
        a_est = normalized_permeability_lmh_bar(
            flow_lmh_observed,
            pressure_virtual,
            tds,
            temp_c,
            PHYS["ro"]["permeate_backpressure_bar"]["value"],
            PHYS["ro"]["cp_factor"]["value"],
            PHYS["ro"]["osmotic_bar_per_g_l"]["value"],
            PHYS["ro"]["temp_coefficient_per_c"]["value"],
        )
        raw_resistance = (pressure_virtual + 0.1) / max(flow_measured, 0.1)
        hydraulic_index = raw_resistance * (8.9e-4 / max(8.9e-4 / viscosity_factor, 1e-8))
        nominal_carbon_load = cumulative_l * PHYS["carbon"]["assumed_chlorine_mg_l"]["value"]
        carbon_exposure_proxy = (
            nominal_carbon_load / PHYS["carbon"]["nominal_exposure_capacity_mg"]["value"]
        )

        # Latent health and exact RUL are kept for audit/evaluation, never estimator input.
        health = {
            "sediment": sediment_health,
            "uf": uf_health,
            "carbon": 1 - carbon_bt,
            "ro": ro_a / PHYS["ro"]["permeability_lmh_bar"]["value"],
            "uv": max(0.0, 1 - 0.3 * fractions["uv"]),
            "alkaliser": max(0.0, 1 - fractions["alkaliser"]),
        }
        row = {
            "unit_id": unit_id,
            "split": split,
            "scenario": scenario_name,
            "ood_fault": fault if ood else "none",
            "day": day,
            "household_size": household,
            "daily_litres_mean_l": daily_litres_mean,
            "tds_in_mg_l": max(10, tds),
            "turbidity_ntu": turbidity,
            "chlorine_mg_l": chlorine,
            "temp_c": temp_c,
            "hardness": water["hardness"],
            "inlet_pressure_bar": inlet_bar,
            "flow_l_h": flow_measured,
            "fill_time_h": fill_time,
            "motor_current_a": current_measured,
            "rpm": rpm_model + rng.normal(0, float(SENSORS["rpm_sigma"]["value"])),
            "current_ripple_a": ripple,
            "outlet_tds_mg_l": max(
                0.0, outlet_tds + rng.normal(0, float(SENSORS["outlet_tds_sigma_mg_l"]["value"]))
            ),
            "pump_runtime_h": pump_runtime,
            "litres_dispensed_l": demand,
            "cumulative_litres": cumulative_l,
            "pressure_virtual_bar": pressure_virtual,
            "membrane_pressure_bar_true": pressure,
            "osmotic_pressure_bar": osmotic_pressure_bar(
                tds, PHYS["ro"]["cp_factor"]["value"], PHYS["ro"]["osmotic_bar_per_g_l"]["value"]
            ),
            "ro_permeability_est_lmh_bar": max(0, a_est),
            "sediment_resistance_index": sediment_dp_pa / max(base_flow_m3_s, 1e-9) / 1e9,
            "uf_resistance_index": uf_dp_pa / max(base_flow_m3_s, 1e-9) / 1e9,
            "carbon_exposure_index": carbon_exposure_proxy,
            "ro_rejection_fraction": rejection,
            "hydraulic_resistance_index": hydraulic_index,
            "raw_resistance_proxy": raw_resistance,
            "feed_flow_l_h": feed_flow,
            "permeate_l_h_true": perm_l_h,
            "reject_l_h_true": reject_l_h,
            "ro_flux_lmh_true": flux,
            "ro_a_true": ro_a,
            "ro_b_true": ro_b,
            "carbon_breakthrough_true": carbon_bt,
            "recovery_true": recovery,
            "starvation_true": starvation,
        }
        for stage in STAGES:
            row[f"health_{stage}_true"] = health[stage]
            row[f"rul_{stage}_d"] = max(0, stage_life[stage] - day)
            row[f"rul_{stage}_l"] = max(0, stage_life[stage] - day) * daily_litres_mean
        for stage, life in stage_life.items():
            row[f"life_{stage}_d"] = life
        data.append(row)
    frame = pd.DataFrame.from_records(data)
    # Ground truth is the first crossing of the configured physical stage threshold.
    threshold_by_stage = {
        "sediment": THRESHOLDS["sediment_health"]["value"],
        "uf": THRESHOLDS["uf_health"]["value"],
        "carbon": THRESHOLDS["carbon_breakthrough_ratio"]["value"],
        "ro": THRESHOLDS["ro_permeability_fraction"]["value"],
        "uv": THRESHOLDS["uv_intensity_fraction"]["value"],
        "alkaliser": THRESHOLDS["alkaliser_capacity_fraction"]["value"],
    }
    state_columns = {
        "sediment": ("health_sediment_true", "below"),
        "uf": ("health_uf_true", "below"),
        "carbon": ("carbon_breakthrough_true", "above"),
        "ro": ("health_ro_true", "below"),
        "uv": ("health_uv_true", "below"),
        "alkaliser": ("health_alkaliser_true", "below"),
    }
    for stage, (column, sense) in state_columns.items():
        values = frame[column].to_numpy()
        threshold = threshold_by_stage[stage]
        crossed = values <= threshold if sense == "below" else values >= threshold
        end_day = int(np.flatnonzero(crossed)[0]) if crossed.any() else int(frame["day"].iloc[-1])
        frame[f"life_{stage}_d"] = end_day
        frame[f"rul_{stage}_d"] = np.maximum(0, end_day - frame["day"].to_numpy())
        frame[f"rul_{stage}_l"] = frame[f"rul_{stage}_d"] * daily_litres_mean
    return frame


def generate_cohort(
    quick: bool = False, full: bool = False, out_dir: Path | None = None
) -> dict[str, pd.DataFrame]:
    """Create deterministic train/validation/test/OOD cohorts, grouped by unit."""
    requested = read_config("model.yaml")["cohorts"]["full" if full else "quick"]
    sizes = {
        "train": requested["train_units"],
        "validation": requested["validation_units"],
        "test": requested["test_units"],
        "ood": requested["ood_units"],
    }
    rng = np.random.default_rng(SEED)
    scenario_names = list(SCENARIOS)
    cohorts: dict[str, pd.DataFrame] = {}
    offset = 0
    for split, n in sizes.items():
        frames = []
        for i in range(n):
            scenario = scenario_names[(i + offset) % len(scenario_names)]
            prefix = {"train": "TR", "validation": "VA", "test": "TE", "ood": "OD"}[split]
            unit_id = f"{prefix}{i:05d}"
            unit_seed = int(rng.integers(0, np.iinfo(np.int32).max))
            frames.append(simulate_unit(unit_id, split, scenario, unit_seed, split == "ood"))
        cohort = pd.concat(frames, ignore_index=True)
        cohorts[split] = cohort
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            cohort.to_parquet(out_dir / f"{split}.parquet", index=False)
        offset += n
    return cohorts
