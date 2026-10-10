import json
import math
import uuid
from collections import defaultdict, deque
from pathlib import Path

DATA = Path(__file__).parents[1] / "app/district/data"


def _positions(value):
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
        yield value[0], value[1]
    elif isinstance(value, list):
        for child in value:
            yield from _positions(child)


def test_gnitc_map_is_attributed_and_clipped_to_500m():
    data = json.loads((DATA / "gnitc_map.geojson").read_text())
    metadata = data["metadata"]
    assert metadata["license"] == "ODbL-1.0"
    assert metadata["attribution"] == "© OpenStreetMap contributors"
    assert {feature["properties"]["kind"] for feature in data["features"]} == {"building", "road"}
    center = metadata["center"]
    for feature in data["features"]:
        for lon, lat in _positions(feature["geometry"]["coordinates"]):
            a = (math.sin(math.radians(lat-center["lat"])/2) ** 2
                 + math.cos(math.radians(center["lat"])) * math.cos(math.radians(lat))
                 * math.sin(math.radians(lon-center["lon"])/2) ** 2)
            assert 2 * 6371008.8 * math.asin(math.sqrt(a)) <= 500.1


def test_checked_in_shift_topology_is_stable_connected_tree_plus_open_tie():
    data = json.loads((DATA / "gnitc_topology.json").read_text())
    nodes = data["nodes"]
    node_ids = {node["id"] for node in nodes}
    assert len(node_ids) == len(nodes)
    for node_id in node_ids:
        try:
            uuid.UUID(node_id)
        except ValueError:
            continue
        raise AssertionError(f"generated UUID leaked into stable ID {node_id}")
    assert {node["role"] for node in nodes} == {"source", "transformer", "load", "junction"}
    assert all(node["rating_provenance"] == "SYNTHETIC_DEMO_ASSUMPTION" for node in nodes)
    buildings = {feature["id"] for feature in json.loads((DATA / "gnitc_map.geojson").read_text())["features"]
                 if feature["properties"]["kind"] == "building"}
    assert {node["building_id"] for node in nodes if node["role"] == "load"} == buildings

    shift_edges = [edge for edge in data["edges"] if edge["kind"] != "tie"]
    assert len(shift_edges) == len(nodes) - 1
    adjacency = defaultdict(set)
    for edge in shift_edges:
        assert edge["from"] in node_ids and edge["to"] in node_ids
        adjacency[edge["from"]].add(edge["to"])
        adjacency[edge["to"]].add(edge["from"])
    reached, queue = set(), deque(["source"])
    while queue:
        current = queue.popleft()
        if current not in reached:
            reached.add(current)
            queue.extend(adjacency[current] - reached)
    assert reached == node_ids

    ties = [edge for edge in data["edges"] if edge["kind"] == "tie"]
    assert len(ties) == 1
    assert ties[0]["normally_open"] is True
    assert ties[0]["provenance"] == "SYNTHETIC_OPERATIONAL_TIE"
    assert all(edge["length_m"] is None for edge in data["edges"] if edge["component_type"] == "DistributionTransformer")
    assert data["engine_version"] == "995004c84c16df7c8ebfd3ddddf3e723a0938a99"
