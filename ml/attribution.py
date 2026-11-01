"""Conservative cause explanations from normalized and raw signals."""

from __future__ import annotations


def explain_cause(
    tds_ratio: float,
    raw_flow_ratio: float,
    permeability_ratio: float,
    hydraulic_ratio: float,
    stage: str,
) -> dict:
    """Explain feed shift vs hydraulic change; sediment/UF attribution remains shared."""
    if stage == "carbon":
        return {"cause": "usage and assumed chlorine exposure", "confidence": "low"}
    if stage in ("sediment", "uf"):
        return {"cause": "shared hydraulic restriction", "confidence": "low"}
    if tds_ratio >= 1.15 and raw_flow_ratio < 0.95 and permeability_ratio >= 0.9:
        return {"cause": "feed water changed", "confidence": "medium"}
    if hydraulic_ratio > 1.2 or permeability_ratio < 0.8:
        return {"cause": "developing restriction or membrane change", "confidence": "medium"}
    return {"cause": "no strong change isolated", "confidence": "low"}
