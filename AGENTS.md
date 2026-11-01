# FilterTwin engineering conventions

## Commands
- `make setup` installs the pinned Python and web dependencies.
- `make quick` runs the deterministic smoke data/model/evidence pipeline.
- `make reproduce` regenerates datasets, models, evaluation and generated docs.
- `make demo` starts the local API and web app; `make test` runs the tests.
- On Windows without GNU Make, run `.scripts\setup.ps1`, `.scripts\quick.ps1`, and `.scripts\demo.ps1`.

## Engineering rules
- Keep the twin pure Python and deterministic for a fixed seed. SI is used internally.
- Every physical parameter belongs in `configs/*.yaml`, with units, plausible range, and evidence class.
- Each physics function documents a hand-worked numeric example; golden calculations live in `tests/`.
- All displayed performance figures come from generated `results/*.json`. Label provenance as SIMULATED, PUBLIC DATA, or BENCH (not yet collected).
- Group splits by unit. Tune on validation only; evaluate OOD once after freezing the pipeline.
- Clearly distinguish simulator-derived hypotheses from bench validation. Never imply water safety certification.
- Keep the default stage graph and telemetry modes configurable assumptions; use no Atomberg marks or proprietary assets.
- Prefer plain, accessible UI copy; provide a useful offline Demo-Safe mode.

