# Bench-rig proposal (not built or safety-reviewed)

This is a proposed instrumented fixture, not a validated lab procedure. Use qualified staff, compatible pressure-rated parts, electrical isolation, and an approved handling procedure for challenge solutions. Do not use challenge water for consumption.

## Instrument classes

- Replaceable sediment, carbon, RO, UF, UV, and alkaliser stages in a configurable bypass manifold.
- Motor current sensor (INA219/ACS-class appropriate to controller waveform), RPM pickup, and logged pump runtime.
- Inline feed/permeate flow sensors, inlet and outlet TDS probes, temperature probe, turbidity sensor, and a ground-truth pressure transducer on the pump/membrane circuit.
- ESP32-class logger with timestamped CSV; the proposed firmware template is in `hardware/firmware/logger.ino`.
- Reservoir, reject restrictor, controlled tank back-pressure valve, drain, leak detection, and independent high/low pressure shutdowns.

## Challenge-water preparation (proposal)

Use standard test dust or controlled kaolin dosing for turbidity; NaCl solutions for TDS; and a measured hypochlorite stock for free chlorine. Verify each prepared batch with calibrated independent instruments. Keep challenge water contained and dispose of it under local lab procedures. No proprietary purifier cartridge or proprietary control interface is assumed.

## Staged run-to-failure plan

1. Characterize a clean baseline across pressure, flow, temperature, TDS, and controller modes.
2. Calibrate current-to-pressure against the ground-truth transducer over repeated pump cycles.
3. Load one sediment cartridge at a time using staged solids, then repeat with UF. Record pressure, flow, current, ripple, and flush recovery.
4. Dose a carbon cartridge with controlled chlorine/organic exposure; measure breakthrough directly with an appropriate free-chlorine assay.
5. Run separate RO fouling, scaling, and chlorine-exposure sequences. Track normalized flux, salt passage, recovery, and cleaning response.
6. Repeat one cause at a time and paired causes across multiple cartridges, controller modes, inlet pressure, and temperature. Blind the estimator to ground truth and freeze its thresholds before holdout runs.
7. Replace stage modules and verify timestamps, calibration, and CSV ingest before a long run.

## BOM classes

Pressure-rated fittings and housings; replaceable cartridges/membrane coupon; controlled pump supply; pressure relief and shutoff; pressure transducer; flow meters; TDS, temperature and turbidity probes; current/RPM acquisition; logger; reservoirs; tubing and containment; calibration solutions; weighing and water-analysis supplies. Exact parts/ranges must be selected from measured maximum operating conditions before procurement.

## Calibration and output

Use `hardware/calibration/fit_calibration.py` for the current-pressure line and RO A/B sweep. It reports RMSE and R² from supplied CSV rows. `hardware/adapter/convert.py` maps the documented sensor CSV to Parquet. Do not call a twin-generated sample BENCH data.

