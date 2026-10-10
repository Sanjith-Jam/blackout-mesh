"""Steady-state AC checks on small declared district graphs (synthetic parameters)."""
import copy
import math
from pathlib import Path

import pytest

from app.district import electrical
from app.district.electrical import check, load_params

PARAMS = load_params(Path(electrical.__file__).with_name("data") / "gnitc_electrical.json")


def edge_states(topology, faults, closed_ties):
    return {edge["id"]: {"closed": not edge["normally_open"] or edge["id"] in closed_ties,
                         "faulted": edge["id"] in faults} for edge in topology["edges"]}


def node(node_id, role, volts, **extra):
    return {"id": node_id, "role": role, "voltage_v": volts, **extra}


def line(edge_id, a, b, volts, length_m, amps, kind="branch", normally_open=False):
    return {"id": edge_id, "from": a, "to": b, "kind": kind, "component_type": "DistributionBranchBase",
            "voltage_v": volts, "length_m": length_m, "rating_a": amps,
            "limit_w": int(math.sqrt(3) * volts * amps), "normally_open": normally_open}


def fixture(load_length_m=50.0, load_amps=100):
    nodes = [node("source", "source", 11000), node("j1", "junction", 11000),
             node("t1", "transformer", 400, rating_va=100000), node("l1", "load", 400, building_id="b1")]
    edges = [line("feeder", "source", "j1", 11000, 100, 100, kind="feeder"),
             {"id": "x1", "from": "t1", "to": "j1", "kind": "branch", "component_type": "DistributionTransformer",
              "voltage_v": None, "length_m": None, "rating_a": None, "limit_w": 100000, "normally_open": False},
             line("lv", "t1", "l1", 400, load_length_m, load_amps)]
    return {"nodes": nodes, "edges": edges}


def run(topology, served, params=PARAMS, symmetric=False, capacity=10**6):
    pytest.importorskip("power_grid_model")
    return check(topology, params, served, edge_states(topology, set(), set()), capacity, symmetric=symmetric)


def test_balanced_regression_matches_unbalanced_model_with_equal_phase_split():
    topology = fixture()
    balanced = run(topology, {"b1": 20000}, symmetric=True)
    unbalanced = run(topology, {"b1": 20000})
    assert balanced["status"] == unbalanced["status"] == "PASSED"
    assert balanced["model"] == "balanced_positive_sequence" and unbalanced["model"] == "unbalanced_three_phase"
    assert abs(balanced["source_p_w"] - unbalanced["source_p_w"]) < 0.05
    assert abs(balanced["min_voltage_pu"] - unbalanced["min_voltage_pu"]) < 1e-6
    # Losses are part of source demand and the balance residual is within tolerance.
    assert balanced["source_p_w"] == pytest.approx(20000 + balanced["loss_w"], abs=1.0)
    assert abs(balanced["balance_residual_w"]) <= PARAMS.balance_tolerance_w
    assert balanced["safety_claim"] == "NONE" and "protection coordination" in balanced["unmodeled_checks"]


def test_long_thin_service_is_rejected_for_undervoltage_even_though_watts_fit():
    topology = fixture(load_length_m=900.0, load_amps=100)
    result = run(topology, {"b1": 40000})
    assert 40000 <= topology["edges"][2]["limit_w"]
    assert result["status"] == "REJECTED"
    assert any(item["limit"] == "voltage" and item["value"] < PARAMS.voltage_limits_pu[0] for item in result["violations"])


def test_single_phase_overload_is_caught_by_unbalanced_model_but_missed_by_aggregate_watts():
    topology = fixture(load_amps=30)
    params = PARAMS.model_copy(update={"phase_split": {"b1": (1.0, 0.0, 0.0)}})
    watts = 15000
    assert watts <= topology["edges"][2]["limit_w"]  # aggregate W check passes
    assert run(topology, {"b1": watts}, params=params, symmetric=True)["status"] == "PASSED"
    unbalanced = run(topology, {"b1": watts}, params=params)
    assert unbalanced["status"] == "REJECTED"
    assert any(item["limit"] == "line_loading" and item["component_id"] == "lv" for item in unbalanced["violations"])


def test_source_budget_includes_losses():
    result = run(fixture(), {"b1": 20000}, capacity=20000)
    assert result["status"] == "REJECTED"
    assert [item["limit"] for item in result["violations"]] == ["source_active_power"]


def test_missing_ratings_or_incompatible_voltage_block_validation():
    topology = fixture()
    missing = copy.deepcopy(topology)
    missing["edges"][2]["length_m"] = None
    assert run(missing, {"b1": 1000})["status"] == "BLOCKED"
    mismatched = copy.deepcopy(topology)
    mismatched["edges"][2]["voltage_v"] = 11000
    result = run(mismatched, {"b1": 1000})
    assert result["status"] == "BLOCKED" and "incompatible voltage" in result["reason"]
    assert check(topology, None, {"b1": 1}, edge_states(topology, set(), set()), 1)["status"] == "BLOCKED"


def test_missing_engine_is_unavailable_and_carries_no_numbers(monkeypatch):
    def absent(name):
        raise electrical.PackageNotFoundError(name)
    monkeypatch.setattr(electrical, "version", absent)
    topology = fixture()
    result = check(topology, PARAMS, {"b1": 1000}, edge_states(topology, set(), set()), 10**6)
    assert result["status"] == "UNAVAILABLE" and result["source_p_w"] is None


def test_open_feeder_leaves_downstream_unenergized_and_null_free_of_fabricated_flow():
    pytest.importorskip("power_grid_model")
    topology = fixture()
    states = edge_states(topology, {"feeder"}, set())
    result = check(topology, PARAMS, {}, states, 10**6)
    assert result["status"] == "PASSED"
    assert result["max_line_loading"] is None and result["max_transformer_loading"] is None


def _pandapower_reference(topology, served):
    pp = pytest.importorskip("pandapower")
    net = pp.create_empty_network(f_hz=PARAMS.frequency_hz)
    buses = {item["id"]: pp.create_bus(net, vn_kv=item["voltage_v"] / 1000) for item in topology["nodes"]}
    s = PARAMS.source
    pp.create_ext_grid(net, buses["source"], vm_pu=s.u_ref_pu, s_sc_max_mva=s.sk_va / 1e6, rx_max=s.rx_ratio)
    for edge in topology["edges"]:
        if edge["component_type"] == "DistributionTransformer":
            t = PARAMS.transformer
            sn = 100000
            pp.create_transformer_from_parameters(net, buses["j1"], buses["t1"], sn_mva=sn / 1e6, vn_hv_kv=11, vn_lv_kv=.4,
                vk_percent=t.uk * 100, vkr_percent=t.pk_w / sn * 100, pfe_kw=0, i0_percent=0, shift_degree=330)
        else:
            kind = PARAMS.line_types[str(edge["voltage_v"])]
            pp.create_line_from_parameters(net, buses[edge["from"]], buses[edge["to"]], length_km=edge["length_m"] / 1000,
                r_ohm_per_km=kind.r_ohm_per_km, x_ohm_per_km=kind.x_ohm_per_km, c_nf_per_km=0, max_i_ka=edge["rating_a"] / 1000)
    q = math.tan(math.acos(PARAMS.power_factor))
    for building, watts in served.items():
        pp.create_load(net, buses["l1"], p_mw=watts / 1e6, q_mvar=watts * q / 1e6)
    pp.runpp(net, algorithm="nr", numba=False, tolerance_mva=1e-10)
    return float(net.res_ext_grid.p_mw.sum()) * 1e6, float(net.res_bus.vm_pu.min())


@pytest.mark.parametrize("length_m,watts,expected", [(50.0, 20000, "PASSED"), (900.0, 40000, "REJECTED")])
def test_accepted_and_rejected_cases_agree_with_pandapower_within_frozen_tolerance(length_m, watts, expected):
    topology = fixture(load_length_m=length_m)
    ours = run(topology, {"b1": watts}, symmetric=True)
    reference_p, reference_v = _pandapower_reference(topology, {"b1": watts})
    assert ours["status"] == expected
    assert abs(ours["source_p_w"] - reference_p) <= 1.0  # frozen: 1 W
    assert abs(ours["min_voltage_pu"] - reference_v) <= 1e-4  # frozen: 1e-4 pu
