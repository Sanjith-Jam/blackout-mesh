"""Synthetic GNITC district study state; no generated wire is a real feeder."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.district.profile import load_profile
from app.district.appliances import inventory_energy, validate_mapping
from app.district import electrical
from app.district.recovery import config_problem, evaluate, optimize
from app.core.active_site import CATALOG

SERVER_EPOCH = str(uuid.uuid4())
EVIDENCE_MIN_SAMPLES = 2
EVIDENCE_DWELL_S = 5
EVIDENCE_MAX_AGE_S = 30

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
        self.decision = {"solver": "integer weighted dispatch", "status": "MODEL_DERIVED",
                         "validation": "WATT_BUDGET_ONLY", "physical_confirmation": None}
        if self.profile.demand_basis == "appliance_inventory":
            validate_mapping(self.profile)
            self.energy_trace = inventory_energy(self.profile)
        self.hour = 12
        self.faults: set[str] = set()
        electrical_path = Path(os.environ.get("DISTRICT_ELECTRICAL", DATA / "gnitc_electrical.json"))
        self.electrical = electrical.load_params(electrical_path) if electrical_path.is_file() else None
        self.closed_ties: frozenset[str] = frozenset()
        self.proposal: dict | None = None
        self.clock = lambda: datetime.now(timezone.utc)
        self.last_observation: tuple[int, datetime] | None = None
        self.evidence: list[tuple[int, datetime]] = []
        self.transformer_scenarios: dict[str, str] = {}
        self.restoration_reason: str | None = None
        self.generation_task_id: str | None = None
        runtime_available, runtime_reason = shift_runtime_probe()
        self.generation = {"status": "CACHED", "available": runtime_available,
            "cluster_count": self.topology["cluster_count"],
            "secondary_strategy": self.topology["secondary_strategy"],
            "reason": f"Cached topology is active; {runtime_reason}",
            "generated_at": None}

    def _electrical_state(self, closed_ties=None):
        states, loads, decision = evaluate(self.topology, self.profile, self.energy_trace, self.hour, self.faults,
                                           self.closed_ties if closed_ties is None else closed_ties)
        if closed_ties is None:
            self.decision = decision
        return states, loads

    def _reset_evidence(self):
        self.evidence = []

    def _evidence_ready(self):
        if len(self.evidence) < EVIDENCE_MIN_SAMPLES:
            return False
        first, last = self.evidence[0][1], self.evidence[-1][1]
        return ((last - first).total_seconds() >= EVIDENCE_DWELL_S
                and (self.clock() - last).total_seconds() <= EVIDENCE_MAX_AGE_S)

    def _record_observation(self, action):
        """Sequenced causal observations; duplicates, reordering and stale samples never count."""
        observation = action.observation
        if observation is None or action.component_id is not None or action.fault_kind is not None:
            return False
        observed_at = datetime.fromisoformat(observation.observed_at)
        if observed_at.tzinfo is None:
            return False
        age = (self.clock() - observed_at).total_seconds()
        if age > EVIDENCE_MAX_AGE_S or age < -2:
            return False
        if self.last_observation and (observation.sequence <= self.last_observation[0]
                                      or observed_at <= self.last_observation[1]):
            return False
        self.last_observation = (observation.sequence, observed_at)
        if observation.healthy:
            self.evidence.append((observation.sequence, observed_at))
        else:
            self._reset_evidence()
            self.restoration_reason = "An unhealthy observation reset the restoration evidence gate."
        return True

    def planning_digest(self):
        """Inputs a proposal depends on; any change makes an earlier proposal stale."""
        return hashlib.sha256(json.dumps({
            "topology": hashlib.sha256(json.dumps(self.topology, sort_keys=True).encode()).hexdigest(),
            "profile": self.profile.config_hash, "electrical": self.electrical.config_hash if self.electrical else None,
            "faults": sorted(self.faults), "closed_ties": sorted(self.closed_ties), "hour": self.hour,
            "energy": self.energy_trace["profile"][self.hour]}, sort_keys=True).encode()).hexdigest()

    def _ac_check(self, closed_ties):
        states, loads = self._electrical_state(closed_ties)
        return electrical.check(self.topology, self.electrical, {load["building_id"]: load["grid_served_w"] for load in loads},
                                states, self.profile.source_capacity_w)

    def _restoration(self, states):
        candidate = (self.proposal or {}).get("candidate_edge_ids")
        reason = self.restoration_reason or "No recovery candidate proposed."
        stale = bool(self.proposal and self.proposal["digest"] != self.planning_digest())
        if stale:
            reason = "Proposal is stale: faults, switches, hour or model inputs changed; propose again."
        return {"candidate_edge_id": min(candidate) if candidate else None, "candidate_edge_ids": candidate or [],
                "applied_edge_id": min(self.closed_ties, default=None), "applied_edge_ids": sorted(self.closed_ties),
                "stable_since": self.evidence[0][1].isoformat() if self.evidence else None,
                "stable_evidence_count": len(self.evidence), "evidence_ready": self._evidence_ready(),
                "evidence_rule": f"{EVIDENCE_MIN_SAMPLES} distinct healthy sequenced observations spanning at least "
                                 f"{EVIDENCE_DWELL_S} s, newest within {EVIDENCE_MAX_AGE_S} s",
                "last_observation_sequence": self.last_observation[0] if self.last_observation else None,
                "reason": reason, "proposal": copy.deepcopy(self.proposal), "proposal_stale": stale, "provenance": "MODEL_DERIVED",
                "physical_confirmation": None}

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
        if name != "record_observation" and getattr(action, "observation", None) is not None:
            return False
        if name == "reset":
            self.__init__()
            return True
        if name == "advance_hour":
            if action.component_id is not None or action.fault_kind is not None:
                return False
            # Demo time steps are not observations and never satisfy the restoration dwell.
            self.hour = (self.hour + 1) % 24
            return True
        if name == "record_observation":
            return self._record_observation(action)
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
                self.faults.remove(edge["id"])
                self.proposal = None
                self.closed_ties = frozenset()
                self._reset_evidence()
            self.restoration_reason = None
            return True
        if name == "propose_recovery":
            if action.component_id is not None or action.fault_kind is not None:
                return False
            result = optimize(self.topology, self.profile, self.energy_trace, self.hour, self.faults,
                              self.closed_ties, self.electrical, electrical.check)
            candidate = result["candidate_edge_ids"]
            if candidate is not None and frozenset(candidate) == self.closed_ties:
                result.update(candidate_edge_ids=None, switching_sequence=[])
                self.restoration_reason = "The current switch configuration is already the best validated configuration."
            elif candidate is None:
                self.restoration_reason = {"UNVALIDATED": "No candidate can be electrically validated: "
                                           + (result["evaluations"][-1]["ac_reason"] if result["evaluations"] else "no permitted configuration."),
                                           "NO_VALIDATED_RECOVERY": "Every permitted configuration failed a declared electrical check."}[result["solver_status"]]
            else:
                self.restoration_reason = (f"{result['solver_status']} candidate under the declared objective; "
                                           "passed the unbalanced AC check. Awaiting fresh healthy evidence.")
            self.proposal = {**result, "proposal_id": str(uuid.uuid4()), "proposed_revision": self.revision,
                             "digest": self.planning_digest()}
            self._reset_evidence()
            return True
        if name == "apply_recovery":
            candidate = (self.proposal or {}).get("candidate_edge_ids")
            if action.component_id is not None or action.fault_kind is not None or not candidate:
                return False
            if not self._evidence_ready():
                return False
            if self.proposal["digest"] != self.planning_digest():
                self.restoration_reason = "Proposal is stale: faults, switches, hour or model inputs changed; propose again."
                return False
            final = frozenset(candidate)
            problem = config_problem(self.topology, self.faults, final)
            ac = self._ac_check(final)
            if problem or ac["status"] != "PASSED":
                self.restoration_reason = f"Revalidation refused the candidate: {problem or ac['reason']}"
                return False
            self.closed_ties = final
            self.proposal = None
            self._reset_evidence()
            self.restoration_reason = "Recovery applied to modeled state after AC revalidation; no physical switch confirmation is available."
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
