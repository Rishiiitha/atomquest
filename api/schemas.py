from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EventInput(BaseModel):
    kind: Literal[
        "silt_spike",
        "tanker_tds_switch",
        "chlorine_breakthrough",
        "cold_snap",
        "pump_wear",
        "usage_change",
    ]
    day: int = Field(default=30, ge=0)
    duration_days: int = Field(default=7, ge=1, le=365)
    value: float | None = None


class SimulateRequest(BaseModel):
    scenario: str = "chennai_municipal"
    seed: int = 20261101
    events: list[EventInput] = Field(default_factory=list)


class WhatIfRequest(BaseModel):
    tds_mg_l: float = Field(ge=0, le=5000)
    temperature_c: float = Field(ge=0, le=60)
    membrane_permeability_lmh_bar: float = Field(default=8.0, ge=0, le=30)
    pressure_bar: float = Field(default=4.5, ge=0, le=12)
    permeate_pressure_bar: float = Field(default=0.15, ge=0, le=5)
    area_m2: float = Field(default=0.4, gt=0, le=2)


class ScenarioSummary(BaseModel):
    id: str
    tds_mg_l: float
    turbidity_ntu: float
    chlorine_mg_l: float
    hardness: float
    temp_c: float


class WhatIfResponse(BaseModel):
    provenance: str
    raw_flux_lmh: float
    raw_flow_l_h: float
    osmotic_pressure_bar: float
    net_driving_pressure_bar: float
    normalized_permeability_lmh_bar: float
    normalized_health_fraction: float
    temperature_corrected: bool


class StageHealth(BaseModel):
    stage: str
    health_fraction: float
    rul_days: float
    rul_litres: float
    interval_days: list[float]
    confidence: Literal["high", "medium", "low"]
    cause: str
    explanation: str
    provenance: Literal["SIMULATED", "PUBLIC DATA", "BENCH (not yet collected)"]


class IngestResponse(BaseModel):
    accepted_rows: int
    provenance: str
    stage_estimates: list[StageHealth]
    notes: list[str]
