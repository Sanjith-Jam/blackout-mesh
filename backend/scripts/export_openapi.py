import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.openapi.utils import get_openapi
from app.main import app

def export():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    
    # Generate operation IDs
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            # Create stable operation IDs from method and path
            operation["operationId"] = operation.get("summary", "").replace(" ", "") or f"{method}_{path.replace('/', '_')}"

    # Also include the WebSocket envelope so it's generated
    from app.schemas.snapshot import WebSocketMessageEnvelope
    envelope_schema = WebSocketMessageEnvelope.model_json_schema(ref_template="#/components/schemas/{model}")
    # fastapi puts nested schemas in $defs, we should merge them
    if "$defs" in envelope_schema:
        for k, v in envelope_schema.pop("$defs").items():
            if k not in openapi_schema["components"]["schemas"]:
                openapi_schema["components"]["schemas"][k] = v
                
    openapi_schema["components"]["schemas"]["WebSocketMessageEnvelope"] = envelope_schema

    out_path = Path(__file__).resolve().parents[2] / "openapi.json"
    with open(out_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

if __name__ == "__main__":
    export()
