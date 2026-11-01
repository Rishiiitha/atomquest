# Claim-validation protocol

| Claim | Bench evidence needed | Holdout method |
|---|---|---|
| Current estimates differential pressure | Repeated pressure sweeps under each controller mode, flow, temperature and pump age | Hold out complete pump units; report RMSE and bias by condition |
| TDS/temperature normalization separates feed stress | Stable clean membrane across controlled TDS and temperature sweeps | Freeze coefficients, evaluate separate cartridges and water batches |
| Sediment and UF signatures differ | One-stage-at-a-time loading with independent pressure taps or transducer | Randomize cartridge and stress order; report confusion and confounders |
| Carbon breakthrough is estimated from exposure | Measure inlet/outlet free chlorine and organics as loading proceeds | Hold out carbon batches and source-water mixtures |
| Carbon oxidation affects RO salt passage | Matched RO membrane control and chlorine-exposed treatment with measured exposure | Replicate membranes; compare salt passage with measurement uncertainty |
| RUL intervals are calibrated | Multiple run-to-failure units per stage and fault family | Group splits by cartridge and lot; no threshold tuning on final test |
| Warning policy reduces waste/failures | Logged replacement policy simulation and prospective shadow trial | Compare counterfactual policies on units not used for fitting |

No claim is passed by the current synthetic sample. The sample only verifies CSV parsing and schema conversion.

