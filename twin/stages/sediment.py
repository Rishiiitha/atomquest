"""Sediment cake filtration equation."""

from twin.physics import cake_pressure_drop_pa


def pressure_drop_pa(
    flow_m3_s: float,
    area_m2: float,
    viscosity_pa_s: float,
    membrane_resistance: float,
    cake_resistance: float = 0.0,
) -> float:
    """Darcy drop for membrane+cake; G4 Rtotal=1e10 gives 7417 Pa."""
    return cake_pressure_drop_pa(
        flow_m3_s, area_m2, viscosity_pa_s, membrane_resistance + cake_resistance
    )


def cake_mass_per_area(
    previous_kg_m2: float,
    capture_efficiency: float,
    solids_kg_m3: float,
    flow_m3_s: float,
    area_m2: float,
    dt_s: float,
) -> float:
    """Integrate dw/dt=η C Q/A; η=.5,C=.001,Q=.00001,A=.02,dt=10 -> increment .0000025 kg/m²."""
    if area_m2 <= 0 or dt_s < 0:
        raise ValueError("area must be positive and time nonnegative")
    return max(0.0, previous_kg_m2 + capture_efficiency * solids_kg_m3 * flow_m3_s / area_m2 * dt_s)
