# Data, schema and provenance

## Generated cohorts

`data/generated/{train,validation,test,ood}.parquet` contains daily rows with unit ID, scenario, observed sensor-like inputs, simulator latent states, exact functional-threshold RUL labels in days and litres, and the stage life used to generate each trajectory. Unit IDs are disjoint across splits. Training and validation use the configured scenario family; test units are held out by unit. OOD units apply unseen fault perturbations (pump wear, air ingress, voltage sag, sensor drift, or partial replacement). The generated data is synthetic and model-dependent.

The exact generated column list and units are recorded in `results/schema.json`. Values are SI internally where applicable; app-facing flow is L/h, pressure bar, TDS mg/L, turbidity NTU, and temperature °C. Train only on observed sensor-derived features: `*_true`, `life_*`, and `rul_*` columns are ground truth and excluded from model input.

## External-source checks (2026-11-01)

| Source | URL | Use | License / status | Limits |
|---|---|---|---|---|
| NASA C-MAPSS PCoE | https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/ | Generic prognostics pipeline / NASA score only | NOT AVAILABLE IN THIS RUN. Direct catalog and archive probes failed DNS resolution; no file was fetched and the license was not verified. The official catalog lookup also indicated the download was unavailable. | Turbofan faults do not validate membrane physics |
| NASA Data.gov listing | https://catalog.data.gov/dataset/c-mapss-aircraft-engine-simulator-data | Availability cross-check | Metadata only; no usable file obtained in this run | Source note says download access is under review |
| CGWB Ground Water Quality | https://cgwb.gov.in/ground-water-quality | Possible regional water priors | NOT AVAILABLE IN THIS RUN. Direct probe failed DNS resolution; no values were ingested and no licence was established. | Annual pre-monsoon monitoring is not household purifier telemetry |
| National Water Data Portal / CGWB | https://www.nwdp.nwic.gov.in/dataset/ground-water-quality-manual-chemical-parameters-cgwb-f-gfg | Candidate TDS/hardness priors | Dataset metadata found; download not ingested in this run; licence not verified | Coverage, stations and measurement dates differ from household feedwater |
| RO fouling studies | https://www.mdpi.com/2673-4117/6/5/98 | Literature consistency check only | NOT AVAILABLE IN THIS RUN. Direct probe failed DNS resolution; no raw compatible series was fetched and the license was not verified. | Plant-scale TMP series is not cartridge-level EOL truth |
| Figshare membrane biofilm record | https://figshare.com/articles/On-line_biofilm_strength_detection_in_cross-flow_membrane_filtration_systems/5729061 | Candidate pressure/fouling observations | Candidate located in catalog search, but direct probe was unavailable; file not imported and license not verified. | Not a household RO run-to-failure dataset |

The standard-library fetch/probe script is `data/fetch_public.py`; the actual reachability report is `results/public_fetch.json`. A source only changes to PUBLIC DATA after a compatible file is downloaded, its license is recorded, and its schema is validated. In this run external validation remains pending.

