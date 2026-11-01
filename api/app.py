"""Evidence-backed local API. All returned forecast metrics are generated artifacts."""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from io import BytesIO
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    EventInput,
    IngestResponse,
    ScenarioSummary,
    SimulateRequest,
    StageHealth,
    WhatIfRequest,
    WhatIfResponse,
)
from hardware.adapter.convert import adapt_frame
from ml.features import TARGETS, add_state_projections, model_features
from twin.physics import (
    normalized_permeability_lmh_bar,
    osmotic_pressure_bar,
    permeate_flow_l_h,
    ro_flux_lmh,
)
from twin.simulator import ROOT, SCENARIOS, simulate_unit

RESULTS = ROOT / "results"
app = FastAPI(
    title="FilterTwin API",
    version="0.1.0",
    description="Simulator-backed maintenance planning prototype.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_results() -> None:
    if (
        not (RESULTS / "metrics.json").exists()
        or not (RESULTS / "test_predictions.parquet").exists()
    ):
        raise HTTPException(503, "Generated evidence is missing; run `make quick` first.")


@lru_cache(maxsize=1)
def _metrics() -> dict:
    _require_results()
    return json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _test() -> pd.DataFrame:
    _require_results()
    return pd.read_parquet(RESULTS / "test_predictions.parquet")


@lru_cache(maxsize=1)
def _models() -> dict:
    model_path = RESULTS / "models"
    if not model_path.exists():
        raise HTTPException(503, "Model artifacts are missing; run `make quick` first.")
    return {stage: joblib.load(model_path / f"{stage}.joblib") for stage in TARGETS}


def _score_simulated_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the frozen tier-C model to a newly simulated trajectory."""
    frame = add_state_projections(frame)
    models = _models()
    for stage in TARGETS:
        features = model_features(frame, physics=True, tier="C", stage=stage)
        state = frame[f"ekf_rul_{stage}_C_d"].to_numpy(dtype=float)
        frame[f"pred_p1_{stage}_d"] = np.maximum(0, state + models[stage]["p1"].predict(features))
    return frame


@app.get("/healthz")
def healthz() -> dict:
    ready = (RESULTS / "metrics.json").exists()
    return {"status": "ready" if ready else "evidence_missing", "provenance": "SIMULATED"}


@app.get("/scenarios", response_model=list[ScenarioSummary])
def get_scenarios() -> list[dict]:
    return [{"id": key, **value} for key, value in SCENARIOS.items()]


@app.get("/units")
def list_units() -> list[dict]:
    frame = _test()
    rows = []
    for unit_id, group in frame.groupby("unit_id", sort=True):
        latest = group.sort_values("day").iloc[-1]
        risk = min(float(latest[f"pred_p1_{s}_d"]) for s in TARGETS)
        rows.append(
            {
                "unit_id": unit_id,
                "scenario": str(latest.scenario),
                "day": int(latest.day),
                "next_rul_days": risk,
                "provenance": "SIMULATED",
            }
        )
    return rows


@app.get("/units/{unit_id}/telemetry")
def telemetry(unit_id: str, limit: int = 200) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(422, "limit must be between 1 and 1000")
    frame = _test()
    subset = frame.loc[frame.unit_id == unit_id].sort_values("day").tail(limit)
    if subset.empty:
        raise HTTPException(404, "unit not found in the generated test cohort")
    columns = [
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
    ]
    return subset[columns].replace({np.nan: None}).to_dict(orient="records")


@app.get("/units/{unit_id}/health", response_model=list[StageHealth])
def unit_health(unit_id: str) -> list[StageHealth]:
    frame = _test()
    rows = frame.loc[frame.unit_id == unit_id].sort_values("day")
    if rows.empty:
        raise HTTPException(404, "unit not found in the generated test cohort")
    row, first = rows.iloc[-1], rows.iloc[0]
    tds_changed = float(row.tds_in_mg_l) > float(first.tds_in_mg_l) * 1.15
    a_est = float(row.ro_permeability_est_lmh_bar)
    a_ref = float(rows.ro_permeability_est_lmh_bar.iloc[: min(7, len(rows))].median())
    flow_delta = float(row.flow_l_h) / max(float(first.flow_l_h), 0.1)
    result = []
    qmetrics = _metrics()
    for stage in TARGETS:
        confidence: Literal["high", "medium", "low"]
        rul = float(row[f"pred_p1_{stage}_d"])
        q = float(qmetrics["stages"][stage]["conformal_q_days_by_horizon"].get("21", 0))
        health = {
            "sediment": float(
                np.clip(
                    1
                    - 0.05
                    * (
                        row.hydraulic_resistance_index / max(first.hydraulic_resistance_index, 0.01)
                        - 1
                    ),
                    0,
                    1,
                )
            ),
            "uf": float(
                np.clip(
                    1
                    - 0.04
                    * (
                        row.hydraulic_resistance_index / max(first.hydraulic_resistance_index, 0.01)
                        - 1
                    ),
                    0,
                    1,
                )
            ),
            "carbon": float(np.clip(1 - row.carbon_exposure_index, 0, 1)),
            "ro": float(np.clip(a_est / 8, 0, 1)),
        }[stage]
        if stage == "carbon":
            cause, confidence, explanation = (
                "Usage and assumed chlorine exposure",
                "low",
                "Carbon breakthrough is not directly measured; this estimate uses litres and a configured chlorine prior.",
            )
        elif stage in ("sediment", "uf"):
            cause, confidence = "Shared hydraulic restriction signal", "low"
            explanation = "Pressure and flow changed together. This signal cannot uniquely distinguish sediment from UF without bench validation."
        elif tds_changed and a_est >= 0.9 * max(a_ref, 1e-4) and flow_delta < 0.95:
            cause, confidence = "Feed water changed", "medium"
            explanation = "Raw flow fell while estimated normalized membrane permeability stayed near its initial level."
        else:
            cause, confidence = "Normalized membrane permeability trend", "medium"
            explanation = "The estimate corrects permeate flow for pressure, osmotic pressure, and temperature."
        daily_litres = float(rows.litres_dispensed_l.tail(14).mean())
        result.append(
            StageHealth(
                stage=stage,
                health_fraction=health,
                rul_days=rul,
                rul_litres=rul * daily_litres,
                interval_days=[max(0, rul - q), rul + q],
                confidence=confidence,
                cause=cause,
                explanation=explanation,
                provenance="SIMULATED",
            )
        )
    return result


@app.post("/simulate")
def simulate(request: SimulateRequest) -> dict:
    if request.scenario not in SCENARIOS:
        raise HTTPException(422, f"unknown scenario {request.scenario}")
    try:
        frame = simulate_unit(
            "LIVE",
            "demo",
            request.scenario,
            request.seed,
            events=[e.model_dump(exclude_none=True) for e in request.events],
        )
        frame = _score_simulated_frame(frame)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "provenance": "SIMULATED",
        "scenario": request.scenario,
        "events": [event.model_dump(exclude_none=True) for event in request.events],
        "readings": frame.to_dict(orient="records"),
    }


@app.post("/whatif", response_model=WhatIfResponse)
def what_if(request: WhatIfRequest) -> dict:
    values = request.model_dump()
    raw_flux = ro_flux_lmh(
        values["membrane_permeability_lmh_bar"],
        values["pressure_bar"],
        values["tds_mg_l"],
        values["temperature_c"],
        values["permeate_pressure_bar"],
    )
    raw_flow = permeate_flow_l_h(raw_flux, values["area_m2"])
    ndp = (
        values["pressure_bar"]
        - values["permeate_pressure_bar"]
        - osmotic_pressure_bar(values["tds_mg_l"])
    )
    normalized = normalized_permeability_lmh_bar(
        raw_flux,
        values["pressure_bar"],
        values["tds_mg_l"],
        values["temperature_c"],
        values["permeate_pressure_bar"],
    )
    return {
        "provenance": "SIMULATED",
        "raw_flux_lmh": raw_flux,
        "raw_flow_l_h": raw_flow,
        "osmotic_pressure_bar": osmotic_pressure_bar(values["tds_mg_l"]),
        "net_driving_pressure_bar": ndp,
        "normalized_permeability_lmh_bar": normalized,
        "normalized_health_fraction": normalized / 8,
        "temperature_corrected": True,
    }


@app.get("/evidence/metrics")
def evidence_metrics() -> dict:
    return _metrics()


@app.get("/evidence/figures")
def evidence_figures() -> dict:
    metrics = _metrics()
    return {
        "provenance": "SIMULATED",
        "stages": metrics["stages"],
        "telemetry_tiers": metrics["telemetry_tiers"],
        "signature_matrix": metrics["signature_matrix"],
        "business_impact": metrics["business_impact"],
    }


@app.get("/evidence/provenance")
def evidence_provenance() -> dict:
    return _metrics()["provenance_legend"] | {
        "external_validation": _metrics()["public_data_checks"]
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "upload a CSV bench log")
    payload = await file.read()
    return _ingest_payload(file.filename, payload)


def _ingest_payload(filename: str, payload: bytes) -> IngestResponse:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(415, "upload a CSV bench log")
    if len(payload) > 8_000_000:
        raise HTTPException(413, "CSV is larger than the prototype ingest limit")
    try:
        source = pd.read_csv(BytesIO(payload))
        frame = adapt_frame(source)
        frame = add_state_projections(frame)
        models = _models()
        estimates = []
        last = frame.iloc[-1]
        daily_litres = float(frame.litres_dispensed_l.tail(14).mean())
        baseline_resistance = max(
            float(frame.hydraulic_resistance_index.iloc[: min(7, len(frame))].median()), 0.01
        )
        health_by_stage = {
            "sediment": float(
                np.clip(
                    1 - 0.05 * (last.hydraulic_resistance_index / baseline_resistance - 1), 0, 1
                )
            ),
            "uf": float(
                np.clip(
                    1 - 0.04 * (last.hydraulic_resistance_index / baseline_resistance - 1), 0, 1
                )
            ),
            "carbon": float(np.clip(1 - last.carbon_exposure_index, 0, 1)),
            "ro": float(np.clip(last.ro_permeability_est_lmh_bar / 8, 0, 1)),
        }
        qmetrics = _metrics()
        for stage in TARGETS:
            bundle = models[stage]
            features = model_features(frame, physics=True, tier="C", stage=stage)
            delta = float(bundle["p1"].predict(features.tail(1))[0])
            rul = max(0.0, float(last[f"ekf_rul_{stage}_d"]) + delta)
            q = float(qmetrics["stages"][stage]["conformal_q_days_by_horizon"].get("21", 0))
            estimates.append(
                StageHealth(
                    stage=stage,
                    health_fraction=health_by_stage[stage],
                    rul_days=rul,
                    rul_litres=rul * daily_litres,
                    interval_days=[max(0, rul - q), rul + q],
                    confidence="low",
                    cause="Bench ingestion path; calibration pending",
                    explanation="CSV parsed and passed through the current feature/model path. The sample is not bench evidence.",
                    provenance="BENCH (not yet collected)",
                )
            )
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"bench CSV could not be mapped: {exc}") from exc
    return IngestResponse(
        accepted_rows=len(frame),
        provenance="BENCH (not yet collected)",
        stage_estimates=estimates,
        notes=["A parsed sample verifies the adapter only; no physical bench data was collected."],
    )


def _apply_ws_controls(
    message: dict, cursor: int, speed: float, paused: bool, frame_length: int
) -> tuple[int, float, bool]:
    """Apply deterministic pause, seek, and speed controls for the websocket stream."""
    kind = message.get("type")
    if kind == "pause":
        paused = bool(message.get("paused", True))
    elif kind == "speed":
        speed = float(np.clip(message.get("value", speed), 1, 1000))
    elif kind == "seek":
        cursor = int(np.clip(message.get("day", cursor), 0, frame_length - 1))
    return cursor, speed, paused


def _row_for_wire(row: pd.Series) -> dict:
    return {
        key: (None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value)
        for key, value in row.items()
    }


@app.websocket("/ws/sim")
async def websocket_sim(ws: WebSocket) -> None:
    await ws.accept()
    scenario = ws.query_params.get("scenario", "chennai_municipal")
    if scenario not in SCENARIOS:
        await ws.send_json({"type": "error", "message": "unknown scenario"})
        await ws.close(code=1008)
        return
    events: list[dict] = []
    frame = simulate_unit("WS", "demo", scenario, 20261101)
    cursor, speed, paused = 0, 20.0, False
    try:
        while cursor < len(frame):
            if paused:
                try:
                    message = await ws.receive_json()
                except WebSocketDisconnect:
                    return
            else:
                await ws.send_json(
                    {"type": "reading", "reading": _row_for_wire(frame.iloc[cursor])}
                )
                cursor += 1
                try:
                    message = await asyncio.wait_for(ws.receive_json(), timeout=1.0 / speed)
                except TimeoutError:
                    continue
                except WebSocketDisconnect:
                    return
            kind = message.get("type")
            if kind == "inject-event":
                event = EventInput.model_validate(message.get("event", {})).model_dump(
                    exclude_none=True
                )
                events.append(event)
                frame = simulate_unit("WS", "demo", scenario, 20261101, events=events)
                cursor = min(int(event["day"]), len(frame) - 1)
                await ws.send_json({"type": "event-accepted", "event": event})
            else:
                cursor, speed, paused = _apply_ws_controls(
                    message, cursor, speed, paused, len(frame)
                )
    except (WebSocketDisconnect, ValueError, KeyError):
        return
