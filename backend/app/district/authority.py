"""Synthetic GNITC district study state; no generated wire is a real feeder."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.district.profile import apportion, load_profile
from app.district.appliances import dispatch, inventory_energy, validate_mapping
from app.core.active_site import CATALOG

SERVER_EPOCH = str(uuid.uuid4())

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
        self.profile = load_profile(Path(os.environ.get("DISTRICT_PROFILE", DATA / "gnitc_profile.json")), self.topology)
        self.map = json.loads((DATA / "gnitc_map.geojson").read_text())
        self.energy_trace = json.loads((DATA / "gnitc_energy.json").read_text())
        self._allocation_cache = None
        self._allocation_key = None
        self.decision = {"solver": "integer weighted dispatch", "status": "MODEL_DERIVED",
                         "validation": "WATT_BUDGET_ONLY", "physical_confirmation": None}
        if self.profile.demand_basis == "appliance_inventory":
            validate_mapping(self.profile)
            self.energy_trace = inventory_energy(self.profile)
        self.hour = 12
        self.faults: set[str] = set()
        self.closed_tie: str | None = None
        self.candidate_tie: str | None = None
        self.stable_evidence_count = 0
        self.stable_since: str | None = None
        self.transformer_scenarios: dict[str, str] = {}
        self.restoration_reason: str | None = None
        self.generation_task_id: str | None = None
        runtime_available, runtime_reason = shift_runtime_probe()
        self.generation = {"status": "CACHED", "available": runtime_available,
            "cluster_count": self.topology["cluster_count"],
            "secondary_strategy": self.topology["secondary_strategy"],
            "reason": f"Cached topology is active; {runtime_reason}",
            "generated_at": None}

    def _electrical_state(self):
        topology = self.topology
        edge_by_id = {edge["id"]: edge for edge in topology["edges"]}
        states = {edge["id"]: {"id": edge["id"], "closed": (not edge["normally_open"] or edge["id"] == self.closed_tie),
                             "faulted": edge["id"] in self.faults, "energized": False, "flow_w": 0}
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

        if self.profile.demand_basis == "appliance_inventory":
            key = (tuple(sorted(parent_edge.items())), tuple((edge["id"], edge["limit_w"]) for edge in topology["edges"]))
            if key != self._allocation_key:
                self._allocation_cache = dispatch(self.profile, topology, parent, parent_edge, source)
                self._allocation_key = key
            flows, loads, self.decision = copy.deepcopy(self._allocation_cache)
            for edge in topology["edges"]:
                state = states[edge["id"]]
                state.update(flow_w=flows[edge["id"]], provenance="MODEL_DERIVED",
                             energized=edge["from"] in parent and edge["to"] in parent and state["closed"] and not state["faulted"])
            return states, loads

        # Allocate the hourly trace using declared per-building policy weights.
        loads = []
        flows = {edge_id: 0 for edge_id in states}
        source_capacity_w = self.profile.source_capacity_w
        grid_served_total = 0
        policies = {row.building_id: row for row in self.profile.buildings}
        requested = sorted((node for node in topology["nodes"] if node["role"] == "load"),
                           key=lambda node: (policies[node.get("building_id", node["id"])].tier != "critical", node["id"]))
        profile = self.energy_trace["profile"][self.hour]
        demand_w = profile["demand_w"]
        grid_requested_total_w = profile["grid_import_w"]
        demands = apportion(demand_w, {key: row.demand_weight for key, row in policies.items()})
        imports = apportion(grid_requested_total_w, demands)
        for node in requested:
            path = []
            cursor = node["id"]
            while cursor in parent_edge:
                edge_id = parent_edge[cursor]
                path.append(edge_id)
                cursor = parent[cursor]
            connected = bool(source) and cursor == source
            policy = policies[node.get("building_id", node["id"])]
            tier = policy.tier
            requested_w = demands[policy.building_id]
            grid_requested_w = imports[policy.building_id]
            # Configured grid-following PV/storage cannot energize an isolated building.
            local_supply_w = requested_w - grid_requested_w if connected else 0
            path_capacity = min((edge_by_id[edge_id]["limit_w"] - flows[edge_id] for edge_id in path), default=source_capacity_w)
            grid_served_w = min(grid_requested_w, source_capacity_w - grid_served_total, max(0, path_capacity)) if connected else 0
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
                          "tier_provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
                          "tier_rationale": policy.rationale,
                          "local_supply_provenance": "MODEL_DERIVED",
                          "local_supply_basis": "CITYLEARN_DISTRICT_ENERGY_BALANCE_RESIDUAL_ALLOCATED_PER_BUILDING",
                          "local_supply_semantics": "CONFIGURED_GRID_FOLLOWING_REQUIRES_SOURCE_REACHABILITY",
                          "grid_service_provenance": "MODEL_DERIVED", "unmet_provenance": "MODEL_DERIVED", "appliances": []})

        for edge in topology["edges"]:
            state = states[edge["id"]]
            state["flow_w"] = flows[edge["id"]]
            state["energized"] = edge["from"] in parent and edge["to"] in parent and state["closed"] and not state["faulted"]
            state["provenance"] = "MODEL_DERIVED"
        return states, loads

    def _tie_joins_components(self, tie_id):
        tie = next((edge for edge in self.topology["edges"] if edge["id"] == tie_id and edge["kind"] == "tie"), None)
        if tie is None:
            return False
        states, _ = self._electrical_state()
        parent = {node["id"]: node["id"] for node in self.topology["nodes"]}
        def root(node):
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node
        for edge in self.topology["edges"]:
            state = states[edge["id"]]
            if edge["id"] == tie_id or not state["closed"] or state["faulted"]:
                continue
            left, right = root(edge["from"]), root(edge["to"])
            if left != right:
                parent[left] = right
        return root(tie["from"]) != root(tie["to"])

    def _restoration(self, states):
        reason = self.restoration_reason or "No recovery candidate proposed."
        if self.candidate_tie:
            tie = next((edge for edge in self.topology["edges"] if edge["id"] == self.candidate_tie), None)
            if tie is None:
                reason = "Candidate tie is absent from the current topology."
            elif not self._tie_joins_components(tie["id"]):
                reason = "Closing the tie would create a loop; the radial constraint rejects it."
            else:
                reason = "Candidate joins separate modeled sections within its synthetic rating."
        return {"candidate_edge_id": self.candidate_tie, "applied_edge_id": self.closed_tie,
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
            elif scenario == "stale_sensor":
                sensor.update(oil_temperature_c=105.0, voltage_v=380.0, current_a=60.0,
                              cooling_ok=False, status="STALE",
                              provenance="CONFIGURED_SIMULATED_ASSUMPTION")
            diagnosis = diagnose_transformer(sensor)
            transformers.append({"component_id": node["id"], "sensor": sensor, "diagnosis": diagnosis})

        profile = self.energy_trace["profile"]
        energy = profile[self.hour]
        return {"schema_version": "district-v2",
            "identity": {"site_id": "gnitc-demo", "run_id": self.run_id, "revision": self.revision,
                         "server_epoch": SERVER_EPOCH, "profile_hash": self.profile.config_hash},
            "profile": {"id": self.profile.id, "config_hash": self.profile.config_hash,
                "demand_basis": self.profile.demand_basis, "local_supply_mode": self.profile.local_supply_mode,
                "catalog_version": CATALOG.version if self.profile.demand_basis == "appliance_inventory" else None,
                "catalog_hash": CATALOG.config_hash if self.profile.demand_basis == "appliance_inventory" else None,
                "appliance_count": sum(len(load["appliances"]) for load in loads),
                "decision": copy.deepcopy(self.decision)},
            "site": {"name": "Guru Nanak Institutions Technical Campus", "center": self.map["metadata"]["center"], "radius_m": 500},
            "map": {"radius_m": self.map["metadata"]["radius_m"],
                "source": self.map["metadata"]["source"], "source_url": self.map["metadata"]["source_url"],
                "attribution": self.map["metadata"]["attribution"], "license": self.map["metadata"]["license"],
                "retrieved": self.map["metadata"]["retrieved"],
                "source_sha256": self.map["metadata"].get("source_sha256", ""), "features": features},
            "topology": topology,
            "generation": copy.deepcopy(self.generation),
            "state": {"hour": self.hour, "source_capacity_w": self.profile.source_capacity_w,
                "source_capacity_provenance": "CONFIGURED_SIMULATED_ASSUMPTION",
                "source_capacity_note": "Synthetic district dispatch limit; not a measured transformer rating.",
                "grid_requested_w": sum(load["grid_requested_w"] for load in loads),
                "grid_served_w": sum(load["grid_served_w"] for load in loads),
                "unmet_w": sum(load["unmet_w"] for load in loads),
                "source_available": any(node["role"] == "source" for node in topology["nodes"]),
                "edges": list(edge_states.values()), "loads": loads,
                "critical_shortfall_w": (sum(item["requested_w"] - item["served_w"] for load in loads for item in load["appliances"]
                    if item["priority_class"] == "hospital_critical") if self.profile.demand_basis == "appliance_inventory"
                    else sum(load["unmet_w"] for load in loads if load["tier"] == "critical")),
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
                self.stable_evidence_count = 0
                self.stable_since = None
            else:
                if edge["id"] not in self.faults:
                    return False
                if self.stable_evidence_count < 2:
                    return False
                self.faults.remove(edge["id"])
                self.candidate_tie = None
                self.closed_tie = None
                self.stable_evidence_count = 0
                self.stable_since = None
            self.restoration_reason = None
            return True
        if name == "propose_recovery":
            if action.component_id is not None or action.fault_kind is not None:
                return False
            self.candidate_tie = None
            self.restoration_reason = None
            states, _ = self._electrical_state()
            _, before_loads = self._electrical_state()
            before_served = sum(load["served_w"] for load in before_loads)
            for candidate in (edge for edge in self.topology["edges"] if edge["kind"] == "tie"):
                if not self._tie_joins_components(candidate["id"]):
                    self.restoration_reason = "Closing the declared tie would create a loop; radial constraint rejects the route."
                    continue
                previous_tie = self.closed_tie
                self.closed_tie = candidate["id"]
                _, proposed_loads = self._electrical_state()
                self.closed_tie = previous_tie
                if sum(load["served_w"] for load in proposed_loads) <= before_served:
                    self.restoration_reason = "The declared tie does not increase served modeled load under source and line limits."
                    continue
                self.candidate_tie = candidate["id"]
                self.restoration_reason = "Candidate joins separate modeled sections and increases served load within synthetic ratings."
                break
            if self.candidate_tie is None:
                self.stable_evidence_count = 0
                self.stable_since = None
                return True
            self.stable_evidence_count = 0
            self.stable_since = None
            return True
        if name == "apply_recovery":
            if action.component_id is not None or action.fault_kind is not None or not self.candidate_tie:
                return False
            if self.stable_evidence_count < 2:
                return False
            if not self._tie_joins_components(self.candidate_tie):
                self.restoration_reason = "Fresh topology evidence shows the candidate would create a loop."
                return False
            candidate = self.candidate_tie
            previous_tie = self.closed_tie
            self.closed_tie = candidate
            proposed_states, proposed_loads = self._electrical_state()
            edge_limits = {edge["id"]: edge["limit_w"] for edge in self.topology["edges"]}
            if (sum(load["grid_served_w"] for load in proposed_loads) > self.profile.source_capacity_w
                    or any(state["flow_w"] > edge_limits[edge_id] for edge_id, state in proposed_states.items())):
                self.closed_tie = previous_tie
                self.restoration_reason = "Fresh capacity evidence rejects the candidate under source or line limits."
                return False
            self.candidate_tie = None
            self.stable_evidence_count = 0
            self.restoration_reason = "Recovery applied to modeled state; no physical switch confirmation is available."
            return True
        if name == "transformer_scenario":
            if action.component_id not in nodes or nodes[action.component_id]["role"] != "transformer":
                return False
            if action.fault_kind not in ("overload", "cooling_failure", "missing_sensor", "stale_sensor", "clear"):
                return False
            if action.fault_kind == "clear":
                self.transformer_scenarios.pop(action.component_id, None)
            else:
                self.transformer_scenarios[action.component_id] = action.fault_kind
            return True
        return False
