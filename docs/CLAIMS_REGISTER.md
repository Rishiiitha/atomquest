# Claims register

| Pitch claim | Evidence artifact | Status |
|---|---|---|
| Osmotic pressure and temperature can explain raw RO flow shifts | Golden tests and `results/physics_golden.json` | Simulated equation check only |
| Pump current can act as a virtual pressure signal | G3 and calibration fit script | To calibrate on bench; controller-mode sensitivity unresolved |
| Physics normalization improves RUL forecasts | P1 vs B1 metrics in `results/metrics.json` | Mixed: P1 has lower 21-day MAE in 3/4 test stages and 2/4 OOD stages; synthetic twin only |
| Sediment and UF signatures are separable | `docs/SIGNATURES.md` | Not established; shared pressure/flow proxy is confounded |
| Carbon exhaustion can be inferred from hydraulics | Model card / low-confidence exposure feature | Not claimed; exposure proxy only |
| Carbon breakthrough can damage RO salt rejection | Twin oxidation coupling (`ro_b_true`) | Simulator hypothesis; bench test required |
| RUL intervals are calibrated | Per-stage horizon coverage in evaluation | Synthetic validation calibration only |
| Replacements and failures can be reduced | Simulated policy comparison in results | Not supported by this run: fewer replacements but 1,777 more simulated failures than fixed schedule |
| Purifier safety is certified by this predictor | None | Explicitly not claimed |
| Bench deployment is ready | Hardware proposal + ingest adapter | Integration path only; no hardware collected |

