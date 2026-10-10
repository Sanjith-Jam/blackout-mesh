from backend.scripts.export_openapi import export


def test_every_http_route_has_stable_json_request_and_response_contract(tmp_path):
    schema = export(tmp_path / "openapi.json")
    assert schema == export(tmp_path / "openapi-second.json")
    operation_ids = []
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_ids.append(operation["operationId"])
            response = operation["responses"]["200"]["content"]["application/json"]["schema"]
            assert response, f"{method.upper()} {path} has no response schema"
            assert "default" in operation["responses"]
            if method in {"post", "put", "patch"}:
                bodyless = method == "post" and path == "/api/v1/hardware/disconnect"
                if not bodyless:
                    assert operation["requestBody"]["content"]["application/json"]["schema"]
    assert len(operation_ids) == len(set(operation_ids))


def test_visualizer_history_policy_and_websocket_schemas_are_exported(tmp_path):
    schemas = export(tmp_path / "openapi.json")["components"]["schemas"]
    for name in (
        "ClassroomDemoResponse", "HospitalDemoResponse", "HardwareStatusResponse",
        "AllocationPolicyUpdateResponse", "HistoryRunsResponse", "HistoryPageResponse",
        "WebSocketMessageEnvelope", "APIErrorResponse",
    ):
        assert name in schemas
