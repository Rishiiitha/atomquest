# Model card

## Intended use

Prototype stage-wise maintenance estimates for engineering investigation. Predictions guide maintenance; they do not certify drinking-water safety. The app labels the estimate as simulator-derived until calibrated and evaluated on real units.

## Model

The P1 prototype adds a scikit-learn `HistGradientBoostingRegressor` residual to a scalar two-state health/rate Kalman filter and physics-normalized sensor-derived features. B1 is the same CPU gradient-boosting family on raw features. B0 schedule and volume counters are explicit baselines. The requested XGBoost and SHAP components are cut; no SHAP values are claimed. The fitted model bundles export as joblib, while ONNX export is cut.

## Data and evaluation

All train/validation/test/OOD rows come from the deterministic simulator. Unit IDs are grouped and disjoint; warning threshold and conformal radii use validation only. OOD perturbations are reported after the model and policy are frozen. In the full run, test 21-day MAE for P1 ranged from 14.13 days (carbon) to 26.66 days (UF); P1 was worse than B1 for sediment. OOD P1 was worse than B1 for sediment and RO, with RO at 25.60 vs 19.04 days. See generated `docs/EVALUATION.md` and the JSON source `results/metrics.json` for all metrics; do not copy stale numbers into pitch materials.

## Calibration and uncertainty

Split-conformal absolute residual radii target nominal 90% coverage at fixed forecast horizons, stratified by stage, horizon, and sensor tier. Small cohort results may show poor empirical coverage. Carbon's exposure estimate is a usage-based proxy because chlorine is not in the proposed telemetry tiers; its confidence must remain lower than directly observed RO permeability. UV and alkaliser are usage-based twin states and are not learned RUL targets.

## Risks and limitations

- A simulator can reward a model for learning its own equations; results do not establish field performance.
- A single pump-current line may change with controller mode, pump age, voltage, temperature, and manufacturing variation.
- Shared pressure/flow changes cannot uniquely attribute sediment vs UF clogging without more instrumentation or controlled bench evidence.
- The twin does not establish microbial safety, contaminant removal, or a safe replacement interval.
- Regional priors and external RO data were not ingested in this run.
- The simulator's prefilter resistance law is a life-fraction proxy; it does not integrate cake deposition or Hermia kinetics into generated trajectories.
- No cause-classification model, sequence baseline, temperature/no-pressure/coupling ablation, or measured edge-device benchmark is included.

