export interface SourceInfo {
  kind: string;
  capacity_w: number;
}

export interface FeederLimits {
  A: number;
  B: number;
}

export interface Service {
  id: string;
  name: string;
  tier: string;
  feeder: "A" | "B";
  watts: number;
  requested: boolean;
  modeled_served: boolean;
  indicator_confirmed: boolean | null;
  model_reason: string;
}

export interface HospitalRoom {
  id: string;
  name: string;
  lighting_service: string;
  led_bit: number;
}

export interface HospitalZone {
  rooms: HospitalRoom[];
}

export interface ClassroomInfo {
  id: string;
  name: string;
  service_id: string;
  rfid_card_registered: boolean;
  led_bit: number;
  load_event_active: boolean;
}

export interface ClassroomZone {
  active_classroom_id: string | null;
  recent_rfid_scan: string | null;
  rfid_reader_status: string;
  classrooms: ClassroomInfo[];
}

export interface FacilityZones {
  hospital: HospitalZone;
  classroom: ClassroomZone;
}

export interface SystemEvent {
  event_id?: string | null;
  run_id?: string | null;
  revision?: number;
  timestamp: string;
  type: string;
  description: string;
}

export type ActivityState = "ACTIVE" | "INACTIVE" | "UNKNOWN";

export interface ActivityPrediction {
  evidence?: {
    temperature_c: number | null;
    humidity_pct: number | null;
    co2_ppm: number | null;
    humidity_ratio: number | null;
  };
  state: ActivityState;
  score: number | null;
  reason: string;
  source: string | null;
  observed_at: string | null;
  model_version: string;
  priority: string;
}

export interface ModelStatus {
  ready: boolean;
  model_version: string;
  model_type: string;
  features: string[];
  data_source: string;
  evaluation: Record<string, unknown>;
  fallback_reason: string | null;
}

export interface ReplayStatus {
  running: boolean;
  index: number;
  length: number;
}

export interface AllocationStatus {
  objective: string;
  critical_shortfall_w: number;
  served_w: number;
  baseline_mask: number;
  safety?: SafetyStatus;
}

export interface ActivityObservation {
  classroom_id: "CR1" | "CR2" | "CR3";
  temperature_c: number | null;
  humidity_pct: number | null;
  co2_ppm: number | null;
  humidity_ratio: number | null;
  observed_at: string;
  source: "RECORDED_REPLAY" | "SIMULATED";
}

export interface Snapshot {
  activity: Record<string, ActivityPrediction>;
  model: ModelStatus;
  replay: ReplayStatus;
  allocation: AllocationStatus;
  control_revision: number;
  published_revision: number;
  site?: SiteIdentity;
  generated_at: string;
  /** Socket messages only: when this copy was sent. generated_at is when the state last changed. */
  sent_at?: string;
  source: SourceInfo;
  feeder_limits_w: FeederLimits;
  requested_mask: number;
  modeled_mask: number;
  proposed_mask: number;
  indicator_command_mask: number | null;
  indicator_confirmed_mask: number | null;
  indicator_mask: number | null;
  hardware_link: string;
  services: Service[];
  zones?: FacilityZones;
  events?: SystemEvent[];
}

export interface HealthResponse {
  status: string;
  application: string;
}

export interface RfidScanResponse {
  accepted: boolean;
  active_classroom_id: string | null;
  classroom_name: string | null;
  service_id: string | null;
  event_type: string;
}

export interface CapacityChangeResponse {
  accepted: boolean;
  new_capacity_w: number;
  control_revision: number;
}

export interface ClassroomLoadResponse {
  accepted: boolean;
  classroom_id: string;
  load_event_active: boolean;
}

export interface FeederChangeResponse {
  accepted: boolean;
  feeder: string;
  available: boolean;
  control_revision: number;
}

export interface ClassroomDemoLoad {
  id: string;
  name: string;
  watts: number;
  essential: boolean;
  served: boolean;
  reason: string;
}

/** One site authority: every projection carries the same run and revision (#3). */
export interface SiteIdentity {
  run_id: string;
  revision: number;
  profile: string;
  catalog_version: string;
}

export interface CommandReceipt {
  command_id: number;
  name: string;
  run_id: string;
  applied_revision: number;
}

export interface SafetyStatus {
  policy_version: string;
  status: "FEASIBLE" | "PROTECTED_SHORTFALL";
  protected_requested_w: number;
  protected_served_w: number;
  protected_shortfall_w: number;
  fallback_order: string[];
}

export interface ClassroomDemoActivity {
  state: "ACTIVE" | "INACTIVE" | "UNKNOWN";
  /** What the model said before the safety guard; state is what the allocator uses. */
  raw_state: "ACTIVE" | "INACTIVE" | "UNKNOWN";
  guard: string | null;
  score: number | null;
  reason: string;
  model_version: string;
  evidence: { temperature_c?: number | null; humidity_pct?: number | null; co2_ppm?: number | null; humidity_ratio?: number | null };
}

export interface ClassroomDemoRoom {
  id: "CR1" | "CR2" | "CR3";
  name: string;
  rfid_active: boolean;
  priority_rank: number | null;
  activity: ClassroomDemoActivity;
  loads: ClassroomDemoLoad[];
}

export type ClassroomDemoActionName = "scan" | "unscan" | "set_capacity" | "normal" | "overload" | "reset"
  | "replay_pause" | "replay_resume" | "replay_step";

export interface ClassroomDemoSnapshot {
  published_revision: number;
  capacity_w: number;
  capacity_range_w: [number, number];
  requested_w: number;
  served_w: number;
  shortfall_w: number;
  selected_classroom_id: "CR1" | "CR2" | "CR3" | null;
  scanned_classroom_ids: ("CR1" | "CR2" | "CR3")[];
  priority_order: ("CR1" | "CR2" | "CR3")[];
  rooms: ClassroomDemoRoom[];
  mode: "SIMULATED";
  safety: SafetyStatus;
  classroom_limit_w: number;
  campus_limit_w: number | null;
  effective_capacity_w: number;
  limited_by: "classroom limit" | "campus feeder B";
  site?: SiteIdentity;
  command?: CommandReceipt;
  model: { ready: boolean; model_version: string; fallback_reason: string | null };
  replay: { running: boolean; index: number; length: number; step_s: number };
  policy: string;
}

export type HospitalDemoScenario = "normal" | "overload" | "cooling_failure" | "upstream_loss" | "missing_sensor";

export interface DiagnosticHypothesis {
  id: string;
  code: string;
  asset_id: string;
  cause: string;
  severity: "critical" | "high" | "medium" | "low" | "normal" | "unknown";
  evidence_score: number;
  sufficiency: "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT";
  supporting_evidence: string[];
  contradicting_evidence: string[];
  recommendation: string;
}

export interface DiagnosticAbstention {
  asset_id: string;
  reason: "INSUFFICIENT_TELEMETRY" | "CONTRADICTORY_EVIDENCE" | "INDISTINGUISHABLE_CAUSES";
  details: string;
  missing_sensors: string[];
  contradictory_readings: string[];
  indistinguishable_candidates: string[];
  next_check_needed: string;
}

/** Telemetry-only (#4) multi-hypothesis (#19) diagnosis: FAULT_DETECTED after two agreeing readings, ALARM on one, ABSTAINED on missing/stale/contradictory data. */
export interface HospitalDemoDiagnosis {
  code: string;
  cause: string;
  severity: string;
  evidence: string[];
  recommendation: string;
  status?: "NORMAL" | "FAULT_DETECTED" | "ALARM" | "ABSTAINED";
  hypotheses?: DiagnosticHypothesis[];
  abstention?: DiagnosticAbstention | null;
  missing?: string[];
  stale?: string[];
}


export type HospitalDemoActionName = "scan" | "unscan" | "set_capacity" | "normal" | "overload" | "reset" | "replay_pause" | "replay_resume" | "replay_step";

export interface HospitalDemoZone {
  id: string;
  name: string;
  rfid_active: boolean;
  priority_rank: number | null;
  activity: {
    state: "ACTIVE" | "UNKNOWN" | "INACTIVE";
    score: number | null;
    reason: string;
    model_version: string;
    evidence: Record<string, number>;
  };
  loads: {
    id: string;
    name: string;
    watts: number;
    essential: boolean;
    served: boolean;
    reason: string;
  }[];
}

export interface HospitalDemoTransformer {
  id: string;
  name: string;
  zone: string;
  rated_current_a: number;
  sensors: {
    current_a?: number | null;
    temperature_c?: number | null;
    input_voltage_v?: number | null;
    output_voltage_v?: number | null;
    cooling_ok: boolean | null;
  };
  diagnosis: HospitalDemoDiagnosis;
  energized: boolean;
  rfid_active: boolean;
  priority_rank: number | null;
  activity: {
    state: "ACTIVE" | "UNKNOWN" | "INACTIVE";
    score: number | null;
    reason: string;
    model_version: string;
    evidence: Record<string, number>;
  };
  loads: HospitalDemoZone['loads'];
}

export interface HospitalDemoSnapshot {
  capacity_w: number;
  capacity_range_w: [number, number];
  requested_w: number;
  served_w: number;
  shortfall_w: number;
  selected_zone_id: string | null;
  scanned_zone_ids: string[];
  priority_order: string[];
  site?: SiteIdentity;
  command?: CommandReceipt;
  transformers: HospitalDemoTransformer[];
  mode: "SIMULATED";
  model: { ready: boolean; model_version: string; fallback_reason: string | null };
  replay: { running: boolean; index: number; length: number; step_s: number };
  policy: string;
}



