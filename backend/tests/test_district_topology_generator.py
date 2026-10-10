import json
from types import SimpleNamespace

import pytest

from gdm.distribution.components import (
    DistributionBranchBase,
    DistributionLoad,
    DistributionTransformer,
    DistributionVoltageSource,
)
from gdm.quantities import Distance
from infrasys import Location

from shift.data_model import EdgeModel, NodeModel
from shift.graph.distribution_graph import DistributionGraph

from scripts import generate_district_topology as generator


def test_topology_generator_defaults_to_preserved_500m_osm_cache():
    assert generator.MAP.name == "gnitc_map_500m.geojson"


def _small_graph():
    graph = DistributionGraph()
    graph.add_nodes([
        NodeModel(name="source", location=Location(x=0, y=0), assets={DistributionVoltageSource}),
        NodeModel(name="primary", location=Location(x=1, y=0), assets=set()),
        NodeModel(name="secondary", location=Location(x=2, y=0), assets=set()),
        NodeModel(name="load", location=Location(x=3, y=0), assets={DistributionLoad}),
    ])
    graph.add_edge("source", "primary", EdgeModel(
        name="source_branch", edge_type=DistributionBranchBase, length=Distance(10, "m")))
    graph.add_edge("primary", "secondary", EdgeModel(
        name="transformer", edge_type=DistributionTransformer))
    graph.add_edge("secondary", "load", EdgeModel(
        name="load_branch", edge_type=DistributionBranchBase, length=Distance(10, "m")))
    return graph


def test_shift_mapping_and_builder_stages_use_synthetic_catalog_deterministically():
    expected = {
        "phase_nodes": 4,
        "voltage_nodes": 4,
        "edge_equipment": 3,
        "system_nodes": 4,
        "system_edges": 3,
    }
    first = generator._run_shift_stages(_small_graph())
    second = generator._run_shift_stages(_small_graph())
    for result in (first, second):
        assert {key: result[key] for key in expected} == expected
        assert result["nodes"]["load"]["phase"] == "ABC"
        assert result["nodes"]["load"]["voltage_v"] == 400
        assert result["edges"]["transformer"]["limit_w"] == 100_000


def test_shift_pin_check_rejects_a_different_checkout(monkeypatch):
    monkeypatch.setattr(generator.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="wrong\n"))
    with pytest.raises(RuntimeError, match="SHIFT source commit mismatch"):
        generator._verify_shift_commit()


def test_generator_serializes_mapper_results_and_synthetic_diagnostics(tmp_path, monkeypatch):
    graph = _small_graph()

    class StubPRSG:
        def __init__(self, **kwargs):
            pass

        def get_distribution_graph(self):
            return graph

    monkeypatch.setattr(generator, "_verify_shift_commit", lambda: None)
    monkeypatch.setattr(generator, "PRSG", StubPRSG)
    map_path = tmp_path / "map.geojson"
    map_path.write_text(json.dumps({"features": [
        {"id": "building-a", "properties": {"kind": "building"},
         "geometry": {"type": "Point", "coordinates": [0.5, 0.1]}},
        {"id": "building-b", "properties": {"kind": "building"},
         "geometry": {"type": "Point", "coordinates": [1.5, 0.1]}},
    ]}))

    result = json.loads(json.dumps(generator.generate(map_path, cluster_count=2)))
    assert result["equipment_stage"].endswith("no simulation or export")
    assert len(result["nodes"]) == 4
    assert {node["phase"] for node in result["nodes"]} == {"ABC"}
    assert {node["voltage_v"] for node in result["nodes"]} == {400, 11_000}
    assert all(node["rating_va"] > 0 for node in result["nodes"])
    assert {edge["voltage_v"] for edge in result["edges"] if edge["component_type"] != "DistributionTransformer"} == {400, 11_000}

