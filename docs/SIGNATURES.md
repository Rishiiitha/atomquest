# Stage signature analysis

The generated matrix is in `results/metrics.json` under `signature_matrix`, with a vector rendering in `docs/figures/signature_matrix.svg`. It compares twelve controlled equation perturbations against a nominal point under simplified fixed-duty and speed-regulated controller assumptions. These are hypotheses, not observations from a real pump. The reported deltas include permeate flow, fill time, current, RPM, current ripple, outlet TDS, pressure, and normalized permeability.

High TDS and low temperature reduce raw flux while ideal normalized permeability remains invariant. RO fouling and the RO scaling proxy reduce normalized permeability. Carbon oxidation primarily raises salt passage. A generic prefilter restriction and pump/inlet disturbances can all reduce flow and perturb pump load; those signatures overlap and require ground-truth bench instrumentation to validate attribution.

The matrix is not a confusion matrix from a trained classifier. Stage attribution classification was cut from this prototype because simulated observables cannot validate real separability. See `DECISIONS.md`.

