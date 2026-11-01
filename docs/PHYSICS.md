# Physics model and parameter provenance

All calculations below are lumped engineering approximations. The default stage topology and pump telemetry assumptions are configurable and are not claims about Atomberg's internal hardware. Model constants and ranges live in `configs/physics.yaml`, `configs/scenarios.yaml`, and `configs/thresholds.yaml`.

## Reverse osmosis

The solution-diffusion water flux is

`Jw = A(t) fT(T) [Pm - Pperm - Δπ]`, where `Δπ = 0.7 bar/(g/L) × TDS[g/L] × CP`.

The empirical temperature factor is `fT = exp(0.0239 (T - 25 °C))`. The twin separately includes the Vogel water-viscosity equation for Darcy-style resistance normalization. Permeate flow is `Qp = Jw × membrane area`. Estimated permeability inverts the same relationship, so a healthy membrane should remain stable as feed TDS and temperature change, provided pressure and flow measurements are adequate.

Golden checks (generated values are in `results/physics_golden.json`): at 600 mg/L, osmotic pressure is 0.504 bar and net driving pressure at 4.5 bar is 3.996 bar; a healthy 8 LMH/bar membrane gives 31.968 LMH and 12.787 L/h over 0.4 m². At 1800 mg/L the flux is 23.904 LMH while normalized permeability remains 8 LMH/bar. A 5.6 LMH/bar membrane produces 22.378 LMH at the lower feed TDS.

Salt passage uses `Js = B(Cm-Cp)` in a lumped concentration-polarization approximation. RO rejection is computed from the permeate and feed concentration. Carbon breakthrough raises the oxidation exposure term and irreversibly increases B. This coupling is simulated, not bench-verified.

## Hydraulic prefilters and pump

The twin computes Darcy pressure drop with `ΔP = μ(Q/A)R`. Prefilter resistance grows using a configured multiplier of a stage life-fraction health proxy, with a silt-shock penalty. The separate cake-mass helper implements `dw/dt = capture_efficiency × C_ss × Q/A` and has a hand-traced test, but it is not integrated into the daily generated trajectories. No Hermia blocking kinetics or independent capture-efficiency fit is claimed. UF uses a separate assumed area/resistance; the simulator does not model a periodic physical flush.

For a diaphragm-style positive-displacement pump, the virtual differential-pressure line is `I = I0 + k ΔP`; the configured coefficients are marked to calibrate on a bench. Rated flow scales with relative RPM and a configured wear efficiency, then pressure slip and suction starvation reduce the available flow. The operating point balances pump flow against membrane permeate and a square-root reject restrictor using a scalar Brent root. A real pump's current law, controller mode, and starvation signature must be identified for each hardware platform.

The simulator is a physics-guided scenario generator, not a first-principles cartridge twin. It does not model UF flush recovery, detailed tank-level/float control, intraday household draws, or a stochastic degradation random walk. See `DECISIONS.md` for the full scope cut list.

## Carbon, UV and alkaliser

Carbon uses a bounded Thomas-style logistic breakthrough function on cumulative chlorine load. The scenario chlorine is latent twin input; the model's product feature uses cumulative litres times a configured assumed chlorine concentration. This mismatch is intentional and is one reason carbon confidence is low. UV intensity and alkaliser capacity follow usage-based degradation in the twin; only the four hydraulically/exposure-inferred stages are included in the learned RUL model.

## Worked Darcy example

The generated `results/physics_golden.json` records the configured Darcy worked example, salt balance, and normalized-health invariant alongside the RO, temperature, and pump checks. Its inputs are fixtures for dimensional arithmetic, not cartridge specifications.

## Named models and limits

Names used are Darcy's law, Ruth cake filtration, Hermia blocking laws, the Thomas breakthrough model, the solution-diffusion RO model, Kozeny-Carman/Ergun, and a scalar health-state Kalman filter. No source-specific coefficients are claimed. See `DECISIONS.md` and `hardware/BENCH_RIG.md` for calibration needs.

