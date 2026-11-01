# Architecture

```mermaid
flowchart TD
  Y[Config YAML: topology, parameters, scenarios] --> T[Pure deterministic twin]
  T --> G[Daily train / validation / test / OOD Parquet]
  G --> F[Observed-feature builder + health-state EKF]
  F --> M[Raw baseline + P1 boosted residual]
  M --> C[Validation conformal + warning policy]
  C --> E[Held-out evidence JSON and replay bundle]
  E --> API[FastAPI typed endpoints]
  E --> UI[React web app / Demo-Safe replay]
  CSV[Bench CSV] --> AD[Schema adapter] --> API
```

The twin is pure with respect to the file system after parameters are loaded; generation owns data I/O. The API serves generated Parquet and JSON, and an optional websocket streams rows from a local replay. The web app can load the checked-in/precomputed gzip replay if the API is unavailable.

