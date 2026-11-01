# Limitations and threats to validity

- **Internal-validity risk:** generated trajectories and labels share the same equations. Forecast metrics may be optimistic and cannot be interpreted as field accuracy.
- **Pump model:** current proportionality, speed behavior, slip, inlet starvation, and current ripple are configurable simplifications. Controller mode and wear may change the relation.
- **Stage topology:** the default order is an assumption. Stage sequence and bypass/flush paths need to be measured on a target product.
- **Observability:** system pressure/flow aggregate sediment, carbon fines, UF restriction, pump wear, and tank backpressure. Stage attribution is an unverified hypothesis.
- **RO chemistry:** osmotic pressure, concentration polarization, recovery, scaling, fouling, rejection, and oxidation are lumped. No detailed mass-transfer or contaminant-removal validation is included.
- **Carbon:** feed chlorine is latent scenario input. The learned model uses a nominal chlorine-by-volume proxy and has lower expected confidence.
- **End of life:** thresholds are configurable assumptions, not manufacturer service limits.
- **Data coverage:** regional scenarios are hand-configured priors; CGWB data was discovered but not ingested. NASA and compatible RO run-to-failure series were not obtained.
- **No hardware or user evidence:** the CSV sample is synthetic and BENCH status remains not collected.
- **Safety:** the model cannot certify potability or microbial safety, and the app warns against using it for that purpose.

