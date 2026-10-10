"""Optional steady-state AC check of one district switch/load decision.

PASSED means the declared simulation checks held for synthetic parameters. It is never an
operational safety approval: protection, inrush, transients and interlocks are not modeled.
"""
from __future__ import annotations

import hashlib
import json
import math
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

UNMODELED = ["protection coordination", "inrush", "transient/dynamic stability", "physical switch interlocks"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class LineType(_Strict):
    r_ohm_per_km: float = Field(gt=0, le=10, allow_inf_nan=False)
    x_ohm_per_km: float = Field(ge=0, le=10, allow_inf_nan=False)
    r0_ohm_per_km: float = Field(gt=0, le=40, allow_inf_nan=False)
    x0_ohm_per_km: float = Field(ge=0, le=40, allow_inf_nan=False)


class SourceParams(_Strict):
    u_ref_pu: float = Field(ge=.9, le=1.1, allow_inf_nan=False)
    sk_va: float = Field(gt=0, allow_inf_nan=False)
    rx_ratio: float = Field(ge=0, le=10, allow_inf_nan=False)
    z01_ratio: float = Field(gt=0, le=10, allow_inf_nan=False)


class TransformerParams(_Strict):
    vector_group: Literal["Dyn11"]
    uk: float = Field(gt=0, lt=1, allow_inf_nan=False)
    pk_w: float = Field(ge=0, allow_inf_nan=False)
    p0_w: float = Field(ge=0, allow_inf_nan=False)
    i0: float = Field(ge=0, lt=1, allow_inf_nan=False)
    no_load_loss_note: StrictStr = ""


class ElectricalParams(_Strict):
    schema_version: Literal["district-electrical-v1"]
    provenance: Literal["SYNTHETIC_ENGINEERING_ASSUMPTION"]
    note: StrictStr
    frequency_hz: Literal[50, 60]
    voltage_basis: Literal["line_to_line_rms"]
    power_factor: float = Field(ge=.8, le=1, allow_inf_nan=False)
    load_model: Literal["constant_power"]
    voltage_limits_pu: tuple[float, float]
    balance_tolerance_w: float = Field(gt=0, le=100, allow_inf_nan=False)
    source: SourceParams
    line_types: dict[str, LineType]
    transformer: TransformerParams
    phase_split: dict[str, tuple[float, float, float]] = {}

    @model_validator(mode="after")
    def check(self):
        low, high = self.voltage_limits_pu
        if not .5 < low < 1 < high < 1.5:
            raise ValueError("voltage limits must bracket 1 pu")
        for building, split in self.phase_split.items():
            if min(split) < 0 or abs(sum(split) - 1) > 1e-9:
                raise ValueError(f"{building}: phase split must be nonnegative and sum to 1")
        return self

    @property
    def config_hash(self):
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_params(path: Path) -> ElectricalParams:
    return ElectricalParams.model_validate_json(path.read_text(encoding="utf-8"))


def _result(status, params, symmetric, **extra):
    return {"status": status, "engine": "power-grid-model", "engine_version": None,
            "model": "balanced_positive_sequence" if symmetric else "unbalanced_three_phase",
            "params_hash": params.config_hash if params else None, "violations": [],
            "min_voltage_pu": None, "max_voltage_pu": None, "max_line_loading": None,
            "max_transformer_loading": None, "source_p_w": None, "source_q_var": None, "loss_w": None,
            "balance_residual_w": None, "reason": None, "unmodeled_checks": UNMODELED,
            "safety_claim": "NONE", **extra}


def build_model(topology, params: ElectricalParams, served_w: dict[str, int], states, symmetric):
    """Serialize declared parameters only; missing or incompatible ratings raise ValueError."""
    from power_grid_model import initialize_array, LoadGenType
    nodes = {node["id"]: node for node in topology["nodes"]}
    ids = {node_id: index for index, node_id in enumerate(sorted(nodes))}
    next_id = len(ids)
    node = initialize_array("input", "node", len(ids))
    node["id"] = list(ids.values())
    for node_id, index in ids.items():
        volts = nodes[node_id].get("voltage_v")
        if not isinstance(volts, (int, float)) or volts <= 0:
            raise ValueError(f"{node_id}: missing voltage base")
        node["u_rated"][index] = float(volts)

    lines, transformers, component = [], [], {}
    for edge in topology["edges"]:
        state = states[edge["id"]]
        # Use the planner's energized flag when present so both models share one reachability.
        status = int(state.get("energized", state["closed"] and not state["faulted"]))
        left, right = nodes[edge["from"]], nodes[edge["to"]]
        if edge.get("component_type") == "DistributionTransformer":
            hv, lv = (left, right) if left["voltage_v"] > right["voltage_v"] else (right, left)
            rating = next((n.get("rating_va") for n in (lv, hv) if n["role"] == "transformer"), None)
            if hv["voltage_v"] == lv["voltage_v"] or not isinstance(rating, (int, float)) or rating <= 0:
                raise ValueError(f"{edge['id']}: transformer ratio or kVA rating missing")
            transformers.append((next_id, ids[hv["id"]], ids[lv["id"]], status, hv["voltage_v"], lv["voltage_v"], rating))
        else:
            volts, length, amps = edge.get("voltage_v"), edge.get("length_m"), edge.get("rating_a")
            if volts != left["voltage_v"] or volts != right["voltage_v"]:
                raise ValueError(f"{edge['id']}: incompatible voltage between endpoints")
            kind = params.line_types.get(str(volts))
            if kind is None or not isinstance(length, (int, float)) or length <= 0 or not isinstance(amps, (int, float)) or amps <= 0:
                raise ValueError(f"{edge['id']}: line type, length or ampacity missing")
            lines.append((next_id, ids[edge["from"]], ids[edge["to"]], status, kind, length / 1000, amps))
        component[next_id] = edge["id"]
        next_id += 1

    line = initialize_array("input", "line", len(lines))
    for row, (cid, a, b, status, kind, km, amps) in enumerate(lines):
        line[row] = (cid, a, b, status, status, kind.r_ohm_per_km * km, kind.x_ohm_per_km * km, 0, 0,
                     kind.r0_ohm_per_km * km, kind.x0_ohm_per_km * km, 0, 0, amps)
    transformer = initialize_array("input", "transformer", len(transformers))
    for row, (cid, hv, lv, status, u1, u2, sn) in enumerate(transformers):
        t = transformer[row]
        t["id"], t["from_node"], t["to_node"], t["from_status"], t["to_status"] = cid, hv, lv, status, status
        t["u1"], t["u2"], t["sn"], t["uk"], t["pk"] = u1, u2, sn, params.transformer.uk, params.transformer.pk_w
        t["i0"], t["p0"], t["winding_from"], t["winding_to"], t["clock"] = params.transformer.i0, params.transformer.p0_w, 2, 1, 11
        t["tap_side"], t["tap_pos"], t["tap_min"], t["tap_max"], t["tap_nom"], t["tap_size"] = 0, 0, 0, 0, 0, 0
        t["r_grounding_to"], t["x_grounding_to"] = 0, 0

    sources = [node_id for node_id, item in nodes.items() if item["role"] == "source"]
    if len(sources) != 1:
        raise ValueError("exactly one slack source is supported")
    source = initialize_array("input", "source", 1)
    source[0]["id"], source[0]["node"], source[0]["status"] = next_id, ids[sources[0]], 1
    source[0]["u_ref"], source[0]["sk"] = params.source.u_ref_pu, params.source.sk_va
    source[0]["rx_ratio"], source[0]["z01_ratio"] = params.source.rx_ratio, params.source.z01_ratio
    next_id += 1

    q_ratio = math.tan(math.acos(params.power_factor))
    by_building = {item.get("building_id", item["id"]): item["id"] for item in nodes.values() if item["role"] == "load"}
    rows = [(building, by_building[building], watts) for building, watts in sorted(served_w.items()) if watts > 0]
    load = initialize_array("input", "sym_load" if symmetric else "asym_load", len(rows))
    for row, (building, node_id, watts) in enumerate(rows):
        split = params.phase_split.get(building, (1 / 3, 1 / 3, 1 / 3))
        p = float(watts) if symmetric else [watts * share for share in split]
        load[row]["id"], load[row]["node"], load[row]["status"] = next_id, ids[node_id], 1
        load[row]["type"] = LoadGenType.const_power
        load[row]["p_specified"] = p
        load[row]["q_specified"] = p * q_ratio if symmetric else [value * q_ratio for value in p]
        next_id += 1
    data = {"node": node, "line": line, "transformer": transformer, "source": source,
            ("sym_load" if symmetric else "asym_load"): load}
    return data, {index: node_id for node_id, index in ids.items()}, component


def check(topology, params: ElectricalParams | None, served_w: dict[str, int], states,
          source_capacity_w: int, *, symmetric=False):
    """One immutable study. Missing engine/parameters never authorize application."""
    if params is None:
        return _result("BLOCKED", None, symmetric, reason="No electrical parameter file is configured.")
    try:
        engine_version = version("power-grid-model")
        from power_grid_model import PowerGridModel, CalculationMethod
        from power_grid_model.validation import assert_valid_input_data
    except (ImportError, PackageNotFoundError):
        return _result("UNAVAILABLE", params, symmetric,
                       reason="Optional power-grid-model engine is not installed (backend/requirements-electrical.txt).")
    try:
        data, node_names, component = build_model(topology, params, served_w, states, symmetric)
    except ValueError as exc:
        return _result("BLOCKED", params, symmetric, engine_version=engine_version, reason=str(exc))
    try:
        assert_valid_input_data(data, calculation_type=0, symmetric=symmetric)
        output = PowerGridModel(data, system_frequency=params.frequency_hz).calculate_power_flow(
            symmetric=symmetric, calculation_method=CalculationMethod.newton_raphson,
            error_tolerance=1e-8, max_iterations=30)
    except Exception as exc:  # noqa: BLE001 - nonconvergence/validation are explicit FAILED results
        return _result("FAILED", params, symmetric, engine_version=engine_version,
                       reason=f"AC solve did not converge or input was rejected: {type(exc).__name__}")

    low, high = params.voltage_limits_pu
    violations, voltages = [], []
    for row in output["node"]:
        if not row["energized"]:
            continue
        for value in ([row["u_pu"]] if symmetric else list(row["u_pu"])):
            voltages.append(float(value))
            if not low <= value <= high:
                violations.append({"limit": "voltage", "component_id": node_names[int(row["id"])],
                                   "value": round(float(value), 4), "limit_value": low if value < low else high, "unit": "pu"})
    loadings = {"line": [], "transformer": []}
    losses = 0.0
    for kind in ("line", "transformer"):
        for row in output.get(kind, []):
            if not row["energized"]:
                continue
            loadings[kind].append(float(row["loading"]))
            losses += float(sum([row["p_from"], row["p_to"]]) if symmetric else row["p_from"].sum() + row["p_to"].sum())
            if row["loading"] > 1:
                violations.append({"limit": f"{kind}_loading", "component_id": component[int(row["id"])],
                                   "value": round(float(row["loading"]), 4), "limit_value": 1.0, "unit": "fraction of rating"})
    load_key = "sym_load" if symmetric else "asym_load"
    source_p = float(output["source"]["p"].sum())
    source_q = float(output["source"]["q"].sum())
    load_p = float(output[load_key]["p"].sum()) if load_key in output and len(output[load_key]) else 0.0
    residual = source_p - load_p - losses
    numbers = voltages + loadings["line"] + loadings["transformer"] + [source_p, source_q, losses]
    if not all(math.isfinite(value) for value in numbers):
        return _result("FAILED", params, symmetric, engine_version=engine_version, reason="Solver returned non-finite values.")
    if source_p > source_capacity_w:
        violations.append({"limit": "source_active_power", "component_id": "source", "value": round(source_p, 1),
                           "limit_value": source_capacity_w, "unit": "W (load plus losses)"})
    if abs(residual) > params.balance_tolerance_w:
        violations.append({"limit": "power_balance", "component_id": "source", "value": round(residual, 3),
                           "limit_value": params.balance_tolerance_w, "unit": "W residual"})
    return _result("REJECTED" if violations else "PASSED", params, symmetric, engine_version=engine_version,
                   violations=violations, min_voltage_pu=min(voltages, default=None), max_voltage_pu=max(voltages, default=None),
                   max_line_loading=max(loadings["line"], default=None),
                   max_transformer_loading=max(loadings["transformer"], default=None),
                   source_p_w=round(source_p, 3), source_q_var=round(source_q, 3), loss_w=round(losses, 3),
                   balance_residual_w=round(residual, 6),
                   reason="Declared steady-state checks held." if not violations else
                   f"Failed declared limit(s): {', '.join(sorted({item['limit'] for item in violations}))}.")
