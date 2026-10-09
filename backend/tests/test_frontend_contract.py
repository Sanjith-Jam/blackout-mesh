"""Frontend fixtures must keep the API's shape (#16 contract check).

Regenerate with: PYTHONPATH=backend python backend/scripts/export_frontend_fixtures.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_frontend_fixtures import FIXTURE_DIR, build  # noqa: E402


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__ if value != "<volatile>" else "volatile"


def test_committed_fixtures_match_the_current_api_shape():
    fresh = build()
    for name, data in fresh.items():
        committed = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert shape(committed) == shape(data), f"{name}.json is stale: run backend/scripts/export_frontend_fixtures.py"
