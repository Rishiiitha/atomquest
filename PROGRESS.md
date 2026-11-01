# Progress

- [x] M0 fresh scaffold and explicit scope cuts
- [x] Physics golden cases G1–G5 and simulator unit tests
- [x] Quick reproducible pipeline (84 grouped units; 63.94 CPU seconds)
- [x] Full pipeline (1,500/300/300/300 units; 2,006,668 daily rows; 1,127.36 CPU seconds)
- [x] Validation-only conformal radii and warning thresholds; one-time test and OOD scoring
- [x] Generated FastAPI schema, OpenAPI TypeScript types, API handler tests, and offline replay bundles
- [x] Web production build, Demo-Safe fallback, 8-route desktop/phone screenshots, and Playwright gates (4 passed)
- [x] Hardware proposal, synthetic calibration adapter sample, data/model/claims docs, and final report
- [x] Python tests (12 passed), Ruff, mypy, and full artifact audit
- [x] Live local HTTP routes (`/healthz`, `/scenarios`, `/evidence/metrics`, `/simulate`, `/whatif`, `/ingest`) and WebSocket pause/seek/resume/event injection smoke checks
- [x] Demo launcher starts FastAPI and Vite from the spaced Windows workspace path; it waits for both ports before printing the URL
- [x] Requested B2 sequence model, trained cause-attribution classifier, SHAP/ONNX and additional ablation scope assessed and cut explicitly in `DECISIONS.md`
- [ ] Browser-to-live-API end-to-end and clean-clone setup-to-demo smoke test (Playwright route checks use the offline path; `TestClient` stalls in the managed Windows runtime)
- [ ] Physical bench validation, 60 fps target-device GPU rendering and Lighthouse performance/accessibility gates (no hardware is available in this run)

All predictive results are SIMULATED. No public time-series values or physical bench readings were imported. See [FINAL_REPORT.md](FINAL_REPORT.md) for headline metrics and risks.
