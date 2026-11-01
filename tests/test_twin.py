from twin.simulator import simulate_unit


def test_simulator_rul_is_first_physical_threshold_crossing():
    frame = simulate_unit("TEST", "test", "chennai_municipal", 7)
    assert frame.unit_id.nunique() == 1
    assert frame.rul_sediment_d.min() == 0
    assert frame.rul_ro_d.min() == 0
    for stage, threshold, column in [
        ("sediment", 0.55, "health_sediment_true"),
        ("uf", 0.55, "health_uf_true"),
        ("carbon", 0.1, "carbon_breakthrough_true"),
        ("ro", 0.6, "health_ro_true"),
        ("uv", 0.7, "health_uv_true"),
        ("alkaliser", 0.1, "health_alkaliser_true"),
    ]:
        life = int(frame[f"life_{stage}_d"].iloc[0])
        assert frame.loc[frame.day == life, f"rul_{stage}_d"].iloc[0] == 0
        value = float(frame.loc[frame.day == life, column].iloc[0])
        assert value <= threshold + 0.02 if stage != "carbon" else value >= threshold - 0.02


def test_generated_unit_inputs_are_finite():
    frame = simulate_unit("FINITE", "test", "winter_north", 19)
    numeric = frame.select_dtypes(include="number")
    assert numeric.notna().all().all()
    assert (frame.flow_l_h >= 0).all()
    assert (frame.rul_ro_d >= 0).all()
