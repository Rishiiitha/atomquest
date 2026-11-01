# FilterTwin: from timers to condition-based maintenance

Household purifier feedwater changes with source, season, and use. A fixed calendar or litre counter cannot tell whether a flow change came from osmotic pressure, temperature, or a developing restriction.

FilterTwin is a configurable digital-twin prototype that combines RO solution-diffusion normalization with a pump-current pressure estimate and a stage-wise health-state model. It compares the water conditions and hydraulic signature to estimate when a cartridge may need attention. The output includes an uncertainty interval and a plain-language explanation.

In the current prototype, every performance chart is SIMULATED. The learned forecasts have not been validated on an Atomberg unit or any household purifier. Carbon is modeled from an assumed exposure proxy, and prefilter-stage attribution may be confounded. This is a maintenance decision aid, not a drinking-water safety certificate.

The next step is a replaceable-stage bench rig with current, flow, TDS, temperature, turbidity, and a ground-truth pressure transducer. That rig can calibrate the virtual pressure line and test whether the signatures survive real pump controllers, feedwater variation, and sensor drift. Only after that evidence should fleet learning or replacement recommendations reach customers.

