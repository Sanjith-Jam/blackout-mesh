import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.openapi.utils import get_openapi
from app.main import app

def export(out_path=None):
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["info"]["x-contract-version"] = app.version

    # IDs derive only from method/path, so descriptions can change without API churn.
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete", "options", "head"}:
                operation["operationId"] = f"{method}_{re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_')}"

    # Also include the WebSocket envelope so it's generated
    from app.schemas.snapshot import WebSocketMessageEnvelope
    envelope_schema = WebSocketMessageEnvelope.model_json_schema(ref_template="#/components/schemas/{model}")
    # fastapi puts nested schemas in $defs, we should merge them
    if "$defs" in envelope_schema:
        for k, v in envelope_schema.pop("$defs").items():
            if k not in openapi_schema["components"]["schemas"]:
                openapi_schema["components"]["schemas"][k] = v

    openapi_schema["components"]["schemas"]["WebSocketMessageEnvelope"] = envelope_schema

    from app.schemas.snapshot import APIErrorResponse
    openapi_schema["components"]["schemas"]["APIErrorResponse"] = APIErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}")
    for path_item in openapi_schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete", "options", "head"}:
                operation.setdefault("responses", {}).setdefault("default", {
                    "description": "API error",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/APIErrorResponse"}}},
                })

    out_path = Path(out_path or Path(__file__).resolve().parents[2] / "openapi.json")
    with open(out_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
        f.write("\n")
    return openapi_schema

if __name__ == "__main__":
    export()
