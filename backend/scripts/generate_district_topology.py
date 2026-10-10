"""Regenerate the checked-in GNITC topology using SHIFT at 995004c84c16df7c8ebfd3ddddf3e723a0938a99.

From the repository root: `python3.12 -m venv .venv-city`,
`.venv-city/bin/python -m pip install -e sources/shift`, then
`.venv-city/bin/python backend/scripts/generate_district_topology.py`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import networkx as nx
from infrasys.quantities import Distance
from shapely.geometry import shape
from shift.data_model import GeoLocation, GroupModel
from shift.graph.prsgb import PRSG
from shift.graph.secondary import MeshSteinerStrategy, RadialStrategy

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "backend/app/district/data/gnitc_map.geojson"
OUTPUT = ROOT / "backend/app/district/data/gnitc_topology.json"
CENTER = GeoLocation(78.659909, 17.161849)
SHIFT_COMMIT = "995004c84c16df7c8ebfd3ddddf3e723a0938a99"
STRATEGIES = {"RadialStrategy": RadialStrategy, "MeshSteinerStrategy": MeshSteinerStrategy}


def _groups(features: list[dict], count: int) -> tuple[list[GroupModel], dict[str, str], dict[str, str]]:
    if not 2 <= count <= 6:
        raise ValueError("cluster_count must be 2..6")
    points = []
    for feature in sorted(features, key=lambda item: item["id"]):
        centroid = shape(feature["geometry"]).centroid
        points.append((feature["id"], GeoLocation(centroid.x, centroid.y)))
    if len(points) < count:
        raise ValueError(f"need at least {count} mapped buildings; found {len(points)}")

    # Deterministic farthest-first seeds and bounded Lloyd steps keep all OSM buildings assigned.
    centers = [points[0][1]]
    while len(centers) < count:
        _, point = max(points, key=lambda item: (min((item[1].longitude-c.longitude)**2 + (item[1].latitude-c.latitude)**2 for c in centers), item[0]))
        centers.append(point)
    assignments = []
    for _ in range(25):
        assignments = [min(range(count), key=lambda i: ((point.longitude-centers[i].longitude)**2 + (point.latitude-centers[i].latitude)**2, i)) for _, point in points]
        groups = [[entry for entry, group in zip(points, assignments) if group == i] for i in range(count)]
        if any(not group for group in groups):
            raise ValueError("deterministic clustering produced an empty group")
        updated = [GeoLocation(sum(entry[1].longitude for entry in group)/len(group), sum(entry[1].latitude for entry in group)/len(group)) for group in groups]
        if updated == centers:
            break
        centers = updated

    members = [sorted(entry[0] for entry in group) for group in groups]
    order = sorted(range(count), key=lambda i: members[i])
    remap = {old: new for new, old in enumerate(order)}
    groups = [groups[i] for i in order]
    centers = [centers[i] for i in order]
    assignments = [remap[i] for i in assignments]
    group_members = {f"group-{i:02}": members[old] for i, old in enumerate(order)}
    return [GroupModel(center=center, points=[point for _, point in group]) for center, group in zip(centers, groups)], group_members


def generate(map_path: Path = MAP, cluster_count: int = 6, secondary_strategy: str = "MeshSteinerStrategy") -> dict:
    geo = json.loads(map_path.read_text())
    buildings = [feature for feature in geo["features"] if feature["properties"]["kind"] == "building"]
    groups, group_members = _groups(buildings, cluster_count)
    strategy = STRATEGIES[secondary_strategy]()
    graph = PRSG(groups=groups, source_location=CENTER, buffer=Distance(20, "m"), offline=True,
                 snap_to_roads=False, secondary_strategy=strategy).get_distribution_graph()._graph
    if not nx.is_tree(graph):
        raise ValueError("SHIFT output must be a connected tree")

    building_points = [(feature["id"], shape(feature["geometry"]).centroid) for feature in buildings]
    descriptors = []
    for raw_id, data in graph.nodes(data=True):
        model = data["node_data"]
        lon, lat = float(model.location.x), float(model.location.y)
        assets = {asset.__name__ for asset in model.assets}
        group_id = min(group_members, key=lambda key: abs(groups[int(key[-2:])].center.longitude-lon) + abs(groups[int(key[-2:])].center.latitude-lat))
        if "DistributionVoltageSource" in assets:
            node_id, role, extra = "source", "source", {"phase": "ABC", "voltage_v": 11000, "rating_va": 1000000}
        elif "DistributionLoad" in assets:
            building_id, _ = min(building_points, key=lambda item: abs(item[1].x-lon) + abs(item[1].y-lat))
            node_id, role, extra = f"load:{building_id}", "load", {"building_id": building_id, "phase": "ABC", "voltage_v": 400, "rating_va": 5000}
        elif raw_id.endswith("_ht"):
            node_id, role, extra = f"junction:{group_id}:primary", "junction", {"group_id": group_id, "side": "primary", "phase": "ABC", "voltage_v": 11000, "rating_va": 100000}
        elif any(edge["edge_data"].edge_type.__name__ == "DistributionTransformer" for *_, edge in graph.edges(raw_id, data=True)):
            node_id, role, extra = f"transformer:{group_id}", "transformer", {"group_id": group_id, "phase": "ABC", "voltage_v": 400, "rating_va": 25000}
        else:
            node_id, role, extra = f"junction:{lon:.7f}:{lat:.7f}", "junction", {"phase": "ABC", "voltage_v": 400, "rating_va": 100000}
        descriptors.append({"raw_id": raw_id, "id": node_id, "role": role,
                            "lon": round(lon, 7), "lat": round(lat, 7), **extra})
    by_id = {}
    for node in descriptors:
        by_id.setdefault(node["id"], []).append(node)
    for node_id, same_place_nodes in by_id.items():
        if len(same_place_nodes) == 1:
            continue
        for node in same_place_nodes:
            neighbors = []
            for neighbor in graph.neighbors(node["raw_id"]):
                n = graph.nodes[neighbor]["node_data"].location
                edge = graph.edges[node["raw_id"], neighbor]["edge_data"]
                neighbors.append((round(n.x, 7), round(n.y, 7), edge.edge_type.__name__,
                                  round(float(edge.length.to("m").magnitude), 2) if edge.length is not None else None))
            signature = json.dumps(sorted(neighbors), separators=(",", ":"))
            node["id"] = f"{node_id}:{hashlib.sha256(signature.encode()).hexdigest()[:8]}"
    node_ids = {node["raw_id"]: node["id"] for node in descriptors}
    if len(set(node_ids.values())) != len(node_ids):
        raise ValueError("duplicate stable node IDs after geometry-signature disambiguation")
    node_rows = [{key: value for key, value in node.items() if key != "raw_id"} |
                 {"rating_provenance": "SYNTHETIC_DEMO_ASSUMPTION"} for node in descriptors]

    edge_rows = []
    for raw_u, raw_v, data in graph.edges(data=True):
        u, v = node_ids[raw_u], node_ids[raw_v]
        edge_type = data["edge_data"].edge_type.__name__
        primary_side = any(node_id.endswith(":primary") for node_id in (u, v))
        is_transformer = edge_type == "DistributionTransformer"
        voltage = None if is_transformer else (11000 if "source" in (u, v) or primary_side else 400)
        edge_rows.append({"id": f"edge:{min(u,v)}:{max(u,v)}", "from": u, "to": v,
                          "kind": "feeder" if "source" in (u, v) else "branch", "component_type": edge_type,
                          "length_m": round(float(data["edge_data"].length.to("m").magnitude), 2) if data["edge_data"].length is not None else None,
                          "phase": "ABC", "voltage_v": voltage, "rating_a": None if is_transformer else (100 if voltage == 11000 else 50),
                          "limit_w": 100000 if voltage == 11000 else 20000, "normally_open": False,
                          "provenance": "SHIFT_SYNTHETIC_GEOMETRY", "rating_provenance": "SYNTHETIC_DEMO_ASSUMPTION"})

    transformer_nodes = sorted((row for row in node_rows if row["role"] == "transformer"), key=lambda row: row["id"])
    if len(transformer_nodes) >= 2:
        left, right = transformer_nodes[0], transformer_nodes[-1]
        dlon, dlat = math.radians(right["lon"]-left["lon"]), math.radians(right["lat"]-left["lat"])
        a = math.sin(dlat/2)**2 + math.cos(math.radians(left["lat"])) * math.cos(math.radians(right["lat"])) * math.sin(dlon/2)**2
        edge_rows.append({"id": "tie:declared-demo", "from": left["id"], "to": right["id"], "kind": "tie",
                          "component_type": "DeclaredSyntheticTie", "length_m": round(2*6371008.8*math.asin(math.sqrt(a)),2),
                          "phase": "ABC", "voltage_v": 400, "rating_a": 50, "limit_w": 20000,
                          "normally_open": True, "provenance": "SYNTHETIC_OPERATIONAL_TIE",
                          "rating_provenance": "SYNTHETIC_DEMO_ASSUMPTION"})
    node_rows.sort(key=lambda row: row["id"])
    edge_rows.sort(key=lambda row: row["id"])
    return {"schema_version": "district-topology-v1", "engine": "SHIFT PRSG", "engine_version": SHIFT_COMMIT,
            "engine_license": "BSD-3-Clause", "secondary_strategy": secondary_strategy, "cluster_count": cluster_count,
            "group_members": group_members,
            "provenance": "SYNTHETIC_GEOMETRY; OSM building centroids are virtual group centers, not electrical asset locations",
            "equipment_stage": "PRSG topology plus explicit synthetic ratings; GDM equipment sizing/export is deferred",
            "nodes": node_rows, "edges": edge_rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=MAP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--clusters", type=int, default=6)
    parser.add_argument("--secondary-strategy", choices=sorted(STRATEGIES), default="MeshSteinerStrategy")
    args = parser.parse_args()
    result = generate(args.map, args.clusters, args.secondary_strategy)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.output}: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
