"""Hand-traced physical relationships used by the purifier twin.

SI is used internally except for explicit LMH, L/h, bar, mg/L, and degree-C inputs.
The equations are lumped approximations, not a claim about a specific product.
"""

from __future__ import annotations

import math

from scipy.optimize import brentq


def osmotic_pressure_bar(
    tds_mg_l: float, cp_factor: float = 1.2, coefficient: float = 0.7
) -> float:
    """Return pi = coefficient * CP * TDS[g/L].

    Hand trace: 600 mg/L = 0.6 g/L; 0.7 * 1.2 * 0.6 = 0.504 bar.
    """
    return coefficient * cp_factor * max(tds_mg_l, 0.0) / 1000.0


def temperature_factor(temp_c: float, coefficient: float = 0.0239) -> float:
    """Empirical flux correction exp(k*(T-25)); at 15 C, exp(-0.239)=0.7874."""
    return math.exp(coefficient * (temp_c - 25.0))


def water_viscosity_pa_s(temp_c: float) -> float:
    """Water viscosity (Vogel form); at 25 C this is about 0.890 mPa.s.

    Hand trace: T=298.15 K; mu=2.414e-5*10**(247.8/(298.15-140))
    = 8.90e-4 Pa.s (rounded).
    """
    kelvin = temp_c + 273.15
    if kelvin <= 140.0:
        raise ValueError("temperature is outside the model's water range")
    return 2.414e-5 * 10 ** (247.8 / (kelvin - 140.0))


def ro_flux_lmh(
    permeability_lmh_bar: float,
    membrane_pressure_bar: float,
    tds_mg_l: float,
    temp_c: float = 25.0,
    permeate_pressure_bar: float = 0.0,
    cp_factor: float = 1.2,
    osmotic_bar_per_g_l: float = 0.7,
    temp_coefficient: float = 0.0239,
) -> float:
    """Solution-diffusion water flux J=A*fT*(Pm-Pperm-pi).

    Hand trace: A=8, Pm=4.5, pi(600)=0.504, Pperm=0, T=25;
    J=8*(4.5-0.504)=31.968 LMH.
    """
    net_driving_pressure = (
        membrane_pressure_bar
        - permeate_pressure_bar
        - osmotic_pressure_bar(tds_mg_l, cp_factor, osmotic_bar_per_g_l)
    )
    return max(
        0.0,
        permeability_lmh_bar * temperature_factor(temp_c, temp_coefficient) * net_driving_pressure,
    )


def permeate_flow_l_h(flux_lmh: float, area_m2: float) -> float:
    """Convert LMH times m^2 to L/h; 31.968*0.4=12.7872 L/h."""
    return max(0.0, flux_lmh) * area_m2


def normalized_permeability_lmh_bar(
    flux_lmh: float,
    membrane_pressure_bar: float,
    tds_mg_l: float,
    temp_c: float = 25.0,
    permeate_pressure_bar: float = 0.0,
    cp_factor: float = 1.2,
    osmotic_bar_per_g_l: float = 0.7,
    temp_coefficient: float = 0.0239,
) -> float:
    """Invert the solution-diffusion equation; healthy result is invariant to feed TDS."""
    ndp = (
        membrane_pressure_bar
        - permeate_pressure_bar
        - osmotic_pressure_bar(tds_mg_l, cp_factor, osmotic_bar_per_g_l)
    )
    factor = temperature_factor(temp_c, temp_coefficient)
    return flux_lmh / (factor * ndp) if ndp > 0 and factor > 0 else 0.0


def virtual_pressure_bar(
    current_a: float, intercept_a: float = 0.35, slope_a_bar: float = 0.22
) -> float:
    """Invert I=I0+k*deltaP; current 1.34 A gives 4.5 bar."""
    if slope_a_bar <= 0:
        raise ValueError("current slope must be positive")
    return max(0.0, (current_a - intercept_a) / slope_a_bar)


def current_from_pressure_a(
    pressure_bar: float, intercept_a: float = 0.35, slope_a_bar: float = 0.22
) -> float:
    """Forward motor load line; 0.35+0.22*4.5=1.34 A."""
    return intercept_a + slope_a_bar * max(pressure_bar, 0.0)


def cake_pressure_drop_pa(
    flow_m3_s: float, area_m2: float, viscosity_pa_s: float, resistance_per_m: float
) -> float:
    """Darcy cake drop mu*(Q/A)*R; with G4 clean terms the result is 7416.7 Pa."""
    if area_m2 <= 0 or viscosity_pa_s < 0 or resistance_per_m < 0:
        raise ValueError("area must be positive and resistance/viscosity nonnegative")
    return viscosity_pa_s * (flow_m3_s / area_m2) * resistance_per_m


def thomas_breakthrough_fraction(
    cumulative_load: float, capacity_load: float, steepness_per_load: float = 0.01
) -> float:
    """Bounded logistic breakthrough proxy; at x=1, fraction=1/(1+e)=0.269."""
    exponent = max(-60.0, min(60.0, steepness_per_load * (cumulative_load - capacity_load)))
    return 1.0 / (1.0 + math.exp(-exponent))


def salt_balance(feed_l_h: float, permeate_l_h: float, recovery: float) -> tuple[float, float]:
    """Return reject flow and concentration factor under steady salt conservation.

    Hand trace: feed=40, recovery=.3 -> permeate=12, reject=28;
    reject concentration factor=1/(1-.3)=1.4286 (assuming salt-free permeate).
    """
    if not 0 <= recovery < 1 or feed_l_h < 0:
        raise ValueError("recovery must be in [0,1) and feed flow nonnegative")
    permeate = feed_l_h * recovery if permeate_l_h <= 0 else min(permeate_l_h, feed_l_h)
    actual_recovery = permeate / feed_l_h if feed_l_h else 0.0
    reject = feed_l_h - permeate
    return reject, 1.0 / max(1.0 - actual_recovery, 1e-12)


def solve_operating_pressure_bar(
    *,
    pump_capacity_l_h: float,
    pump_slip_per_bar: float,
    reject_coefficient_l_h_sqrt_bar: float,
    permeability_lmh_bar: float,
    area_m2: float,
    tds_mg_l: float,
    temp_c: float,
    permeate_pressure_bar: float,
    max_pressure_bar: float = 8.0,
    cp_factor: float = 1.2,
    osmotic_bar_per_g_l: float = 0.7,
    temp_coefficient: float = 0.0239,
) -> tuple[float, float, float]:
    """Solve pump capacity = permeate + reject using a scalar pressure root.

    The unit test uses a deterministic operating point and verifies mass balance.
    For each trial pressure, pump slip lowers supply while membrane and restrictor
    flows rise. This simple balance is not a detailed pump curve.
    """

    def residual(p_bar: float) -> float:
        q_pump = pump_capacity_l_h * max(0.1, 1 - pump_slip_per_bar * p_bar)
        q_perm = permeate_flow_l_h(
            ro_flux_lmh(
                permeability_lmh_bar,
                p_bar,
                tds_mg_l,
                temp_c,
                permeate_pressure_bar,
                cp_factor,
                osmotic_bar_per_g_l,
                temp_coefficient,
            ),
            area_m2,
        )
        q_reject = reject_coefficient_l_h_sqrt_bar * math.sqrt(max(0.0, p_bar))
        return q_pump - q_perm - q_reject

    lo, hi = 0.01, max_pressure_bar
    if residual(lo) * residual(hi) > 0:
        raise ValueError("configured pump and system have no operating point in pressure range")
    pressure = brentq(residual, lo, hi, xtol=1e-10)
    permeate = permeate_flow_l_h(
        ro_flux_lmh(
            permeability_lmh_bar,
            pressure,
            tds_mg_l,
            temp_c,
            permeate_pressure_bar,
            cp_factor,
            osmotic_bar_per_g_l,
            temp_coefficient,
        ),
        area_m2,
    )
    reject = reject_coefficient_l_h_sqrt_bar * math.sqrt(pressure)
    return pressure, permeate, reject
