# FilterTwin prototype: final report

## Executive result

The end-to-end prototype and synthetic evaluation are complete. The full deterministic CPU pipeline generated **2,006,668 daily rows** for 1,500 train, 300 validation, 300 test, and 300 OOD units, with unit IDs disjoint across splits. It took **1,127.36 seconds**. All predictive, warning, calibration, hardware-adapter, and fleet-policy results below are **SIMULATED**. No compatible public time series or physical bench measurements were imported.

The physics-normalized P1 model does not win consistently against raw-feature B1. At a 21-day horizon it wins on 3/4 synthetic test stages and 2/4 OOD stages. The most concerning OOD result is RO: P1 MAE is 25.60 days versus 19.04 for B1. The simulated FilterTwin replacement policy also produces 1,777 more cartridge failures than the fixed schedule. These results do not support field-performance or business-savings claims.

## Forecast results

21-day RUL MAE, in days (lower is better):

| Stage | Test P1 | Test B1 | OOD P1 | OOD B1 |
|---|---:|---:|---:|---:|
| Sediment | 25.99 | 24.14 | 20.28 | 18.32 |
| UF | 26.66 | 27.30 | 24.07 | 25.60 |
| Carbon | 14.13 | 16.28 | 13.30 | 15.25 |
| RO | 17.39 | 19.36 | 25.60 | 19.04 |

The nominal split-conformal target is 90%. Test coverage at 21 days ranges from 86.0% (carbon) to 91.0% (UF); sediment is 87.7% and RO is 90.3%. The corresponding P1 interval radii are broad: 23.57–68.09 days. These are simulator-only calibration results, not reliability guarantees. Tier A performance is materially poorer than tier C; see the full telemetry-tier table in [EVALUATION.md](docs/EVALUATION.md).

## Warning and fleet-policy results

Warning thresholds were selected on validation to meet a target of at most 0.25 false alarms per unit-year. Validation recall is 100% for each stage. On the held-out test split, false alarms per unit-year are 0.188 sediment, 0.197 UF, 0.220 carbon, and 0.175 RO. Median warning lead is **zero days** for sediment and UF, so their recall does not provide useful advance notice. On OOD, all four false-alarm rates exceed the target: 0.331, 0.293, 0.265, and 0.391 respectively. OOD RO misses 4 of 300 units (1.33%).

Three-year policy simulation (1,000 households):

| Policy | Useful life wasted | Replacements | Failures | Fail before replacement |
|---|---:|---:|---:|---:|
| Fixed schedule | 17.80% | 18,003 | 7,723 | 42.90% |
| Volume counter | 22.44% | 20,278 | 8,588 | 42.35% |
| FilterTwin | 1.30% | 15,704 | 9,500 | 60.49% |

FilterTwin has 2,299 fewer replacements and 1,777 more failures than the fixed schedule in this simulation. The replacement logic needs redesign and safety-oriented validation before any policy claim.

## Delivered and verified

- Lumped RO/hydraulic simulator, golden physics cases G1–G5, deterministic grouped cohorts, P1/B1/B0 comparisons, validation-only calibration and threshold selection, OOD scoring, and generated evaluation artifacts.
- FastAPI schema and generated TypeScript API types; simulation, what-if, ingest, health, scenario, and WebSocket control paths; offline replay data and Demo-Safe browser views.
- Eight browser routes, desktop and phone screenshots, 48 event replays, and a synthetic 24-row hardware adapter/calibration fixture. The current calibration fixture fit has 0.015 A RMSE and R² 0.99972; this is not a physical pump calibration.
- Python tests: **12 passed**. Ruff passed. Mypy passed for 14 API/data/script source files. Production web build passed. Playwright: **4 passed**, including all routes and the WebGL context-loss fallback. The Three.js runtime is lazy-loaded; its minified chunk is 988 KB (278 KB gzip), and the build reports a large-chunk warning.
- Model bundles are about 366–371 KB per stage. CPU inference measured about 0.0033–0.0047 ms/row on this machine; treat this as a local microbenchmark only.

## Acceptance gates

| Gate | Outcome |
|---|---|
| G1–G5 physics golden checks, deterministic grouped split, full generated cohorts | Passed |
| Validation-only model/policy selection, held-out test and OOD reports | Passed for the synthetic pipeline |
| Production TypeScript/Vite build, all eight routes, desktop/phone screenshots, reduced-motion and offline fallback | Passed; 4 Playwright tests passed |
| Python tests, Ruff, Mypy | Passed: 12 tests, Ruff clean, Mypy clean for 14 API/data/script files |
| External NASA/RO/water-quality dataset acquisition and validation | Not available in this run; no external values ingested |
| Physical bench calibration, run-to-failure data, and real-device accuracy | Not run; hardware kit is a proposal and fixtures are synthetic |
| Live FastAPI HTTP routes and WebSocket stream controls | Passed locally: GET health/scenarios/evidence; POST simulate/what-if/ingest; WebSocket pause/seek/resume/event injection |
| Demo launcher from the spaced workspace path | Passed with installed dependencies: FastAPI and Vite both listened successfully |
| Browser-to-live-API integration and clean-clone `setup` → `demo` smoke test | Not verified in this managed Windows runtime |
| B2 sequence model, trained cause-attribution classifier, requested normalization/coupling ablations, SHAP, ONNX | Cut; see [DECISIONS.md](DECISIONS.md) |
| 60 fps on integrated GPU, native WebGL rendering, Lighthouse ≥90 | Not measured; headless Chromium verified the 2D recovery path only |

To start the app on Windows, run `.\scripts\setup.ps1`, then `.\scripts\demo.ps1`. On a machine with GNU Make, the corresponding commands are `make setup` and `make demo`. A fresh-clone run of either sequence was not part of this verification.

## Unverified gates and limitations

- Network probes for NASA C-MAPSS, CGWB values, and candidate RO time series failed DNS resolution. No external dataset was downloaded, licensed, validated, or used. See [public_fetch.json](results/public_fetch.json) and [DATA.md](docs/DATA.md).
- Live local API checks passed independently: health, scenarios, evidence, simulate, what-if, bench CSV ingest, and WebSocket pause/seek/resume/event injection. Starlette's thread-backed `TestClient` still stalls in this managed Windows runtime, so API unit tests call handlers directly. Browser tests exercise offline data and mock the API as unavailable; a browser-to-live-API end-to-end run remains unverified.
- Headless Chromium verified that a lost WebGL context switches to a labeled 2D schematic. Native GPU rendering, target-device frame rate, and accessibility review on physical devices remain unmeasured.
- The daily twin simplifies pump/controller behavior, filter resistance, carbon exposure, RO chemistry, and stage attribution. Sediment and UF causes are confounded. The configured EOL thresholds are proposals; the model cannot establish water safety.

## Top five risks for a judging review

1. **Simulator dependence:** training labels and forecasts share the same simplified equations; there is no field dataset or physical run-to-failure validation.
2. **OOD reliability:** RO P1 is worse than B1 by 6.56 days at 21 days, and OOD warning false-alarm rates exceed the selected budget at every stage.
3. **Warning usefulness and uncertainty:** sediment and UF have zero-day median test lead; conformal test coverage can fall below 90%, and intervals remain wide.
4. **Policy outcome:** the simulated FilterTwin policy reduces replacements while increasing failures by 1,777 versus the fixed schedule.
5. **Observability and deployment gaps:** stage-level causes are not uniquely observable from aggregate daily sensors; carbon depends on an assumed exposure proxy; live API transport and native hardware/GPU behavior remain unverified.

## Artifacts

- Detailed stage, tier, warning, policy, runtime and compute metrics: [EVALUATION.md](docs/EVALUATION.md)
- Machine-readable scores and cohort metadata: [metrics.json](results/metrics.json)
- Scope and decision log: [DECISIONS.md](DECISIONS.md)
- Claims boundaries: [CLAIMS_REGISTER.md](docs/CLAIMS_REGISTER.md)
- Current gate checklist: [PROGRESS.md](PROGRESS.md)
- Screenshots: [docs/screenshots](docs/screenshots)

## Next engineering work

First, collect bench data across controller modes, pump age, inlet pressure, cartridge states, and paired faults. Confirm cartridge EOL thresholds with product engineering. Then rebuild the evaluation around held-out hardware units, revise warning thresholds against OOD false alarms and useful lead-time requirements, and rerun the policy simulation with failure costs and safety constraints. Keep the app in simulator/demo mode until those gates and live service integration are validated.
