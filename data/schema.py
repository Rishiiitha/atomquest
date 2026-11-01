"""Canonical generated/bench schema metadata."""

UNITS = {
    "flow_l_h": "L/h",
    "tds_in_mg_l": "mg/L",
    "outlet_tds_mg_l": "mg/L",
    "turbidity_ntu": "NTU",
    "temp_c": "degC",
    "pressure_virtual_bar": "bar",
    "motor_current_a": "A",
    "rpm": "rev/min",
    "rul_*_d": "days",
    "rul_*_l": "L",
}
REQUIRED_BENCH_COLUMNS = (
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
)
