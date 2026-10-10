"""Synthetic GNITC district study state; no generated wire is a real feeder."""
from __future__ import annotations

import copy
import json
import subprocess
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("data")
SHIFT_PYTHON = Path(__file__).resolve().parents[3] / ".venv-city/bin/python"


def diagnose_transformer(sensor):
    """Apply simple thresholds to fresh observations; scenario labels are not inputs."""
    if (sensor.get("status") not in {"SIMULATED", "OBSERVED"}
            or any(sensor.get(field) is None for field in
                   ("oil_temperature_c", "voltage_v", "current_a", "cooling_ok"))):
        return {"status": "UNKNOWN", "suspected_part": None,
                "evidence": ["Fresh complete transformer observations are unavailable."]}
    if sensor["cooling_ok"] is False:
        return {"status": "SUSPECTED", "suspected_part": "cooling_system",
                "evidence": ["Observed cooling status is not OK."]}
    if sensor["oil_temperature_c"] >= 100 and sensor["current_a"] >= 50:
        return {"status": "SUSPECTED", "suspected_part": "winding",
                "evidence": ["Observed oil temperature is at least 100 °C and current is at least 50 A."]}
    return {"status": "UNKNOWN", "suspected_part": None,
            "evidence": ["Fresh observations do not meet a configured suspicion threshold."]}


@lru_cache(maxsize=1)
def shift_runtime_probe():
    if not SHIFT_PYTHON.is_file():
        return False, "optional `.venv-city` SHIFT runtime is unavailable."
    try:
        subprocess.run([str(SHIFT_PYTHON), "-c", "import shift, networkx, shapely, infrasys"],
                       check=True, capture_output=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"SHIFT runtime import probe failed: {type(exc).__name__}."
    return True, "optional SHIFT regeneration is available."


class DistrictAuthority:
    def __init__(self):
        self.run_id = str(uuid.uuid4())
        self.revision = 1
        self.topology = json.loads((DATA / "gnitc_topology.json").read_text())
        self.map = json.loads((DATA / "gnitc_map.geojson").read_text())
        self.energy_trace = json.loads((DATA / "gnitc_energy.json").read_text())
        self.hour = 12
        self.faults: set[str] = set()
        self.closed_tie: str | None = None
        self.candidate_tie: str | None = None
        self.stable_evidence_count = 0
        self.stable_since: str | None = None
        self.evidence_signature = None
        self.source_capacity_w = 6000
        self.transformer_scenarios: dict[str, str] = {}
        self.restoration_reason: str | None = None
        self.generation_task_id: str | None = None
        runtime_available, runtime_reason = shift_runtime_probe()
        self.generation = {"status": "CACHED", "available": runtime_available,
            "cluster_count": self.topology["cluster_count"],
            "secondary_strategy": self.topology["secondary_strategy"],
            "reason": f"Cached topology is active; {runtime_reason}",
            "generated_at": None}

    def _electrical_state(self, *, tie_id=..., faults=None, enforce_limits=True):
        tie_id = self.closed_tie if tie_id is ... else tie_id
        faults = self.faults if faults is None else faults
        topology = self.topology
        edge_by_id = {edge["id"]: edge for edge in topology["edges"]}
        states = {edge["id"]: {"id": edge["id"], "closed": (not edge["normally_open"] or edge["id"] == tie_id),
                             "faulted": edge["id"] in faults, "energized": False, "flow_w": 0}
                  for edge in topology["edges"]}
        adjacency = {}
        for edge in topology["edges"]:
            state = states[edge["id"]]
            if state["closed"] and not state["faulted"]:
                adjacency.setdefault(edge["from"], []).append((edge["to"], edge["id"]))
                adjacency.setdefault(edge["to"], []).append((edge["from"], edge["id"]))

        sources = sorted(node["id"] for node in topology["nodes"] if node["role"] == "source")
        source = sources[0] if sources else None
        parent, parent_edge = ({source: None}, {}) if source else ({}, {})
        queue = [source] if source else []
        for current in queue:
            for neighbor, edge_id in sorted(adjacency.get(current, [])):
                if neighbor not in parent:
                    parent[neighbor], parent_edge[neighbor] = current, edge_id
                    queue.append(neighbor)

        # Split this hour's whole-district CityLearn totals deterministically by stable building ID.
        loads = []
        flows = {edge_id: 0 for edge_id in states}
        source_capacity_w = self.source_capacity_w
        grid_served_total = 0
        requested = sorted((node for node in topology["nodes"] if node["role"] == "load"),
                           key=lambda node: (node.get("building_id", node["id"])))
        profile = self.energy_trace["profile"][self.hour]
        count = len(requested)
        demand_w = profile["demand_w"]
        grid_requested_total_w = profile["grid_import_w"]
        demand_base, demand_extra = divmod(demand_w, count) if count else (0, 0)
        grid_base, grid_extra = divmod(grid_requested_total_w, count) if count else (0, 0)
        for index, node in enumerate(requested):
            path = []
            cursor = node["id"]
            while cursor in parent_edge:
                edge_id = parent_edge[cursor]
                path.append(edge_id)
                cursor = parent[cursor]
            connected = bool(source) and cursor == source
            tier = "critical" if index < 3 else "noncritical"
            requested_w = demand_base + (index < demand_extra)
            grid_requested_w = grid_base + (index < grid_extra)
            # CityLearn provides a district residual, allocated per building for this graph view.
            local_supply_w = requested_w - grid_requested_w
            path_capacity = min((edge_by_id[edge_id]["limit_w"] - flows[edge_id] for edge_id in path), default=source_capacity_w)
            grid_served_w = min(grid_requested_w, source_capacity_w - grid_served_total, max(0, path_capacity)) if connected else 0
            if connected and not enforce_limits:
                grid_served_w = grid_requested_w
            if grid_served_w:
                grid_served_total += grid_served_w
                for edge_id in path:
                    flows[edge_id] += grid_served_w
            served_w = local_supply_w + grid_served_w
            loads.append({"building_id": node.get("building_id", node["id"]), "tier": tier,
                          "requested_w": requested_w, "local_supply_w": local_supply_w,
                          "grid_requested_w": grid_requested_w, "grid_served_w": grid_served_w,
                          "served_w": served_w, "unmet_w": requested_w - served_w,
                          "demand_provenance": self.energy_trace["provenance"],
                          "local_supply_provenance": "MODEL_DERIVED",
                          "local_supply_basis": "CITYLEARN_DISTRICT_ENERGY_BALANCE_RESIDUAL_ALLOCATED_PER_BUILDING",
                          "local_supply_semantics": "BEHIND_THE_METER_ALLOCATION_NO_FEEDER_PATH_REQUIRED",
                          "grid_service_provenance": "MODEL_DERIVED", "unmet_provenance": "MODEL_DERIVED"})

        for edge in topology["edges"]:
            state = states[edge["id"]]
            state["flow_w"] = flows[edge["id"]]
            state["energized"] = edge["from"] in parent and edge["to"] in parent and state["closed"] and not state["faulted"]
            state["provenance"] = "MODEL_DERIVED"
        return states, loads

    def _configuration_reason(self, tie_id, faults=None):
        """Check the entire closed graph, including islands, before routing requests."""
        faults = self.faults if faults is None else faults
        parent = {node["id"]: node["id"] for node in self.topology["nodes"]}
        def root(node):
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node
        if sum(node["role"] == "source" for node in self.topology["nodes"]) != 1:
            return "Restoration requires exactly one declared modeled source."
        for edge in self.topology["edges"]:
            if edge["id"] in faults or (edge["normally_open"] and edge["id"] != tie_id):
                continue
            left, right = root(edge["from"]), root(edge["to"])
            if left == right:
                return "Closing the route would create a loop; the radial constraint rejects it."
            parent[left] = right
        # Check requested routing before dispatch clipping hides an overloaded route.
        states, loads = self._electrical_state(tie_id=tie_id, faults=faults, enforce_limits=False)
        if sum(load["grid_served_w"] for load in loads) > self.source_capacity_w:
            return "Source capacity rejects the requested restoration route."
        for edge in self.topology["edges"]:
            if states[edge["id"]]["flow_w"] > edge["limit_w"]:
                return f"Line capacity rejects the requested restoration route: {edge['id']}."
        return None

    def _candidate_reason(self, tie_id):
        tie = next((edge for edge in self.topology["edges"] if edge["id"] == tie_id), None)
        if tie is None or tie["kind"] != "tie" or not tie["normally_open"]:
            return "Candidate is not a declared normally-open tie in the current topology."
        if tie_id in self.faults:
            return "Candidate tie is faulted."
        reason = self._configuration_reason(tie_id)
        if reason:
            return reason
        _, before = self._electrical_state()
        _, after = self._electrical_state(tie_id=tie_id)
        if sum(load["served_w"] for load in after) <= sum(load["served_w"] for load in before):
            return "The declared tie does not increase served modeled demand."
        return None

    def _evidence_key(self):
        return json.dumps([self.topology, sorted(self.faults), self.closed_tie,
                           self.candidate_tie, self.source_capacity_w], sort_keys=True)

    def _reset_evidence(self):
        self.stable_evidence_count = 0
        self.stable_since = None
        self.evidence_signature = self._evidence_key()

    def _evidence_ready(self):
        if self.evidence_signature != self._evidence_key():
            self._reset_evidence()
            self.restoration_reason = "Topology or capacity changed; fresh stable evidence is required."
            return False
        if self.stable_evidence_count < 2:
            self.restoration_reason = "Two fresh stable modeled evidence intervals are required."
            return False
        return True

    def _restoration(self, states):
        reason = self.restoration_reason or "No recovery candidate proposed."
        if self.candidate_tie:
            reason = self._candidate_reason(self.candidate_tie) or reason
        return {"candidate_edge_id": self.candidate_tie, "applied_edge_id": self.closed_tie,
                "physical_confirmed_edge_id": None,
                "stable_since": self.stable_since, "stable_evidence_count": self.stable_evidence_count,
                "reason": reason, "provenance": "MODEL_DERIVED"}

    def snapshot(self):
        topology = copy.deepcopy(self.topology)
        features = []
        for feature in self.map["features"]:
            geometry = feature["geometry"]
            coords = geometry["coordinates"]
            if geometry["type"] in ("LineString", "Polygon"):
                paths = [coords] if geometry["type"] == "LineString" else coords
            elif geometry["type"] == "MultiPolygon":
                paths = [ring for polygon in coords for ring in polygon]
            else:
                paths = coords
            features.append({"id": feature["id"], "kind": feature["properties"]["kind"],
                "name": feature["properties"].get("name"), "geometry_type": geometry["type"],
                "paths": [{"coordinates": path} for path in paths]})

        edge_states, loads = self._electrical_state()
        transformers = []
        for node in topology["nodes"]:
            if node["role"] != "transformer":
                continue
            scenario = self.transformer_scenarios.get(node["id"])
            sensor = {"oil_temperature_c": None, "voltage_v": None, "current_a": None,
                      "cooling_ok": None, "status": "MISSING", "provenance": "NO_SENSOR_DATA"}
            diagnosis = None
            if scenario in ("overload", "cooling_failure"):
                sensor.update(oil_temperature_c=105.0, voltage_v=380.0, current_a=60.0,
                              cooling_ok=scenario != "cooling_failure", status="SIMULATED",
                              provenance="CONFIGURED_SIMULATED_ASSUMPTION")
            diagnosis = diagnose_transformer(sensor)
            transformers.append({"component_id": node["id"], "sensor": sensor, "diagnosis": diagnosis})

        profile = self.energy_trace["profile"]
        energy = profile[self.hour]
        return {"schema_version": "district-v1",
            "identity": {"site_id": "gnitc-demo", "run_id": self.run_id, "revision": self.revision},
            "site": {"name": "Guru Nanak Institutions Technical Campus", "center": self.map["metadata"]["center"], "radius_m": 500},
            "map": {"source": self.map["metadata"]["source"], "source_url": self.map["metadata"]["source_url"],
                "attribution": self.map["metadata"]["attribution"], "license": self.map["metadata"]["license"],
                "retrieved": self.map["metadata"]["retrieved"],
                "source_sha256": self.map["metadata"].get("source_sha256", ""), "features": features},
            "topology": topology,
            "generation": copy.deepcopy(self.generation),
            "state": {"hour": self.hour, "source_capacity_w": self.source_capacity_w,
                "source_capacity_provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
                "source_capacity_note": "Synthetic district dispatch limit; not a measured transformer rating.",
                "grid_requested_w": sum(load["grid_requested_w"] for load in loads),
                "grid_served_w": sum(load["grid_served_w"] for load in loads),
                "unmet_w": sum(load["unmet_w"] for load in loads),
                "source_available": any(node["role"] == "source" for node in topology["nodes"]),
                "edges": list(edge_states.values()), "loads": loads,
                "critical_shortfall_w": sum(load["unmet_w"] for load in loads if load["tier"] == "critical"),
                "faults": [{"component_id": edge_id, "kind": "line_open",
                            "provenance": "CONFIGURED_SIMULATED_ASSUMPTION"} for edge_id in sorted(self.faults)],
                "restoration": self._restoration(edge_states), "transformers": transformers},
            "energy": {"hour": self.hour, "profile": copy.deepcopy(profile),
                "battery_soc_wh": energy["battery_soc_wh"], "engine": self.energy_trace["engine"],
                "provenance": self.energy_trace["provenance"], "pv_used_w": energy["pv_used_w"],
                "battery_charge_w": energy["battery_charge_w"], "battery_discharge_w": energy["battery_discharge_w"],
                "grid_import_w": energy["grid_import_w"],
                "totals": {"period_hours": len(profile), "demand_wh": self.energy_trace["totals"]["demand_wh"],
                    "pv_generated_wh": sum(row["pv_w"] for row in profile),
                    "pv_used_wh": sum(row["pv_used_w"] for row in profile),
                    "pv_curtailed_wh": self.energy_trace["totals"]["pv_curtailed_wh"],
                    "baseline_import_scheduled_wh": self.energy_trace["totals"]["baseline_import_wh"],
                    "dispatch_import_scheduled_wh": self.energy_trace["totals"]["dispatch_import_wh"],
                    "grid_export_wh": 0,
                    "battery_charge_wh": sum(row["battery_charge_w"] for row in profile),
                    "battery_discharge_wh": sum(row["battery_discharge_w"] for row in profile),
                    "battery_loss_wh": self.energy_trace["totals"]["battery_loss_wh"],
                    "battery_round_trip_efficiency": self.energy_trace["battery"]["round_trip_efficiency"]},
                "network_interval": {"duration_hours": 1,
                    "requested_wh": sum(load["requested_w"] for load in loads),
                    "local_supply_wh": sum(load["local_supply_w"] for load in loads),
                    "grid_import_requested_wh": sum(load["grid_requested_w"] for load in loads),
                    "grid_served_wh": sum(load["grid_served_w"] for load in loads),
                    "served_wh": sum(load["served_w"] for load in loads),
                    "unmet_wh": sum(load["unmet_w"] for load in loads),
                    "unmet_fraction_of_requested": float(sum(load["unmet_w"] for load in loads) /
                                                           max(1, sum(load["requested_w"] for load in loads)))}}}

    def apply_action(self, action):
        name = action.action.value
        edges = {edge["id"]: edge for edge in self.topology["edges"]}
        nodes = {node["id"]: node for node in self.topology["nodes"]}
        if name == "reset":
            self.__init__()
            return True
        if name == "advance_hour":
            if action.component_id is not None or action.fault_kind is not None:
                return False
            self.hour = (self.hour + 1) % 24
            if self.candidate_tie or self.faults:
                if self.evidence_signature != self._evidence_key():
                    self._reset_evidence()
                self.stable_evidence_count += 1
                self.stable_since = self.stable_since or datetime.now(timezone.utc).isoformat()
            return True
        if name in ("inject_fault", "clear_fault"):
            edge = edges.get(action.component_id)
            if edge is None or edge["kind"] == "tie" or action.fault_kind != "line_open":
                return False
            if name == "inject_fault":
                if edge["id"] in self.faults:
                    return False
                self.faults.add(edge["id"])
                self._reset_evidence()
            else:
                if edge["id"] not in self.faults:
                    return False
                if not self._evidence_ready():
                    return False
                reason = self._configuration_reason(None, self.faults - {edge["id"]})
                if reason:
                    self.restoration_reason = reason
                    return False
                self.faults.remove(edge["id"])
                self.candidate_tie = None
                self.closed_tie = None
                self._reset_evidence()
            self.restoration_reason = None
            return True
        if name == "propose_recovery":
            if action.component_id is not None or action.fault_kind is not None:
                return False
            self.candidate_tie = None
            self.restoration_reason = None
            for candidate in sorted((edge for edge in self.topology["edges"] if edge["kind"] == "tie"),
                                    key=lambda edge: edge["id"]):
                reason = self._candidate_reason(candidate["id"])
                if reason:
                    self.restoration_reason = reason
                    continue
                self.candidate_tie = candidate["id"]
                self.restoration_reason = "Candidate increases served demand within radial/source/line limits."
                break
            self._reset_evidence()
            return True
        if name == "apply_recovery":
            if action.component_id is not None or action.fault_kind is not None or not self.candidate_tie:
                return False
            if not self._evidence_ready():
                return False
            reason = self._candidate_reason(self.candidate_tie)
            if reason:
                self.restoration_reason = reason
                self._reset_evidence()
                return False
            self.closed_tie = self.candidate_tie
            self.candidate_tie = None
            self._reset_evidence()
            self.restoration_reason = "Recovery applied to modeled state; no physical switch confirmation is available."
            return True
        if name == "transformer_scenario":
            if action.component_id not in nodes or nodes[action.component_id]["role"] != "transformer":
                return False
            if action.fault_kind not in ("overload", "cooling_failure", "missing_sensor", "clear"):
                return False
            if action.fault_kind == "clear":
                self.transformer_scenarios.pop(action.component_id, None)
            else:
                self.transformer_scenarios[action.component_id] = action.fault_kind
            return True
        return False
