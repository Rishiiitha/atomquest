"""Write the FastAPI schema for generated TypeScript API types."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.app import app  # noqa: E402 -- import after adding the project root to sys.path

target = ROOT / "api" / "openapi.json"
target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(target)
