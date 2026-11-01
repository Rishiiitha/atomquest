import math

import numpy as np

from ml.estimator import ScalarHealthEKF
from ml.features import split_conformal_radius
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


def test_g1_ro_normalization_hand_traced():
    # Hand values: pi(600)=.504 bar; NDP=3.996; J=31.968; q=12.7872.
    flux_600 = ro_flux_lmh(8, 4.5, 600)
    assert math.isclose(osmotic_pressure_bar(600), 0.504, rel_tol=0.005)
    assert math.isclose(flux_600, 31.968, rel_tol=0.005)
    assert math.isclose(permeate_flow_l_h(flux_600, 0.4), 12.7872, rel_tol=0.005)
    flux_1800 = ro_flux_lmh(8, 4.5, 1800)
    assert math.isclose(osmotic_pressure_bar(1800), 1.512, rel_tol=0.005)
    assert math.isclose(flux_1800, 23.904, rel_tol=0.005)
    estimated = normalized_permeability_lmh_bar(flux_1800, 4.5, 1800)
    assert math.isclose(estimated / 8, 1.0, rel_tol=0.005)
    fouled = ro_flux_lmh(5.6, 4.5, 600)
    assert math.isclose(fouled, 22.3776, rel_tol=0.005)
    assert math.isclose(normalized_permeability_lmh_bar(fouled, 4.5, 600) / 8, 0.7, rel_tol=0.005)


def test_g2_temperature_hand_trace():
    # Vogel values: ~.890 mPa.s at 25 C and ~1.138 mPa.s at 15 C.
    mu25 = water_viscosity_pa_s(25)
    mu15 = water_viscosity_pa_s(15)
    assert math.isclose(mu25, 0.000890, rel_tol=0.02)
    assert math.isclose(mu15, 0.001135, rel_tol=0.02)
    assert abs((mu25 / mu15) / math.exp(0.0239 * (15 - 25)) - 1) < 0.02
    assert math.isclose(temperature_factor(15), 0.7874, rel_tol=0.005)


def test_g3_virtual_pressure_hand_trace():
    # I=.35+.22*4.5=1.34 A, and inverse returns 4.5 bar.
    amps = current_from_pressure_a(4.5)
    assert math.isclose(amps, 1.34, rel_tol=0.005)
    assert math.isclose(virtual_pressure_bar(amps), 4.5, rel_tol=0.005)


def test_g4_darcy_cake_hand_trace():
    # Q=1 L/min, area=.02 m2, mu=.89 mPa.s, R=1e10 -> 7416.7 Pa.
    flow = 1e-3 / 60
    clean = cake_pressure_drop_pa(flow, 0.02, 0.89e-3, 1e10)
    cake = cake_pressure_drop_pa(flow, 0.02, 0.89e-3, 6e10)
    assert math.isclose(clean, 7416.6667, rel_tol=0.005)
    assert math.isclose(cake, 44500, rel_tol=0.005)


def test_g5_ro_health_invariant_and_salt_balance():
    # A healthy A=8 must invert to 8 across the scenario range (ideal sensors).
    for tds in np.linspace(100, 2500, 20):
        for temp in np.linspace(10, 35, 8):
            flux = ro_flux_lmh(8, 4.5, float(tds), float(temp))
            a_est = normalized_permeability_lmh_bar(flux, 4.5, float(tds), float(temp))
            assert abs(a_est / 8 - 1) < 0.01
    reject, concentration_factor = salt_balance(40, 12, 0.3)
    assert math.isclose(40, 12 + reject, rel_tol=1e-12)
    assert math.isclose(concentration_factor, 1 / 0.7, rel_tol=1e-12)


def test_ekf_projection_numeric_example():
    ekf = ScalarHealthEKF(0.9, initial_rate=0.01)
    assert math.isclose(ekf.project_rul_days(0.6), 30.0, rel_tol=0.005)
    health, rate = ekf.update(0.9)
    assert health > 0.89
    assert rate > 0


def test_split_conformal_radius():
    # For |errors|=0..98, the finite-sample 90% order statistic is 89.
    radius = split_conformal_radius(np.arange(99), 0.9)
    assert radius == 89
    assert np.mean(np.abs(np.arange(99)) <= radius) >= 0.9
