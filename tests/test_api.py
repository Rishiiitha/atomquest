from __future__ import annotations

from pathlib import Path

from api import app as api
from api.schemas import EventInput, SimulateRequest, WhatIfRequest
from twin.simulator import ROOT


def test_typed_api_evidence_and_unit_flow():
    assert api.healthz()["status"] == "ready"
    assert len(api.get_scenarios()) >= 8

    units = api.list_units()
    assert units
    unit_id = units[0]["unit_id"]
    assert api.telemetry(unit_id, limit=20)
    health = api.unit_health(unit_id)
    assert {row.stage for row in health} == {"sediment", "uf", "carbon", "ro"}
    assert all(row.provenance == "SIMULATED" for row in health)
    assert api.evidence_figures()["provenance"] == "SIMULATED"


def test_simulation_whatif_and_bench_csv_ingest():
    simulated = api.simulate(
        SimulateRequest(
            scenario="chennai_municipal",
            seed=9,
            events=[EventInput(kind="silt_spike", day=30)],
        )
    )
    assert "pred_p1_ro_d" in simulated["readings"][0]

    whatif = api.what_if(WhatIfRequest(tds_mg_l=1800, temperature_c=25))
    assert whatif["normalized_health_fraction"] > 0

    sample = Path(ROOT, "hardware", "samples", "bench_like.csv").read_bytes()
    ingested = api._ingest_payload("bench_like.csv", sample)
    assert ingested.accepted_rows > 0
    assert ingested.provenance == "BENCH (not yet collected)"


def test_websocket_can_pause_seek_and_resume():
    cursor, speed, paused = 1, 20.0, False
    for command in (
        {"type": "pause", "paused": True},
        {"type": "seek", "day": 5},
        {"type": "pause", "paused": False},
    ):
        cursor, speed, paused = api._apply_ws_controls(
            command, cursor, speed, paused, frame_length=20
        )
    assert (cursor, speed, paused) == (5, 20.0, False)
