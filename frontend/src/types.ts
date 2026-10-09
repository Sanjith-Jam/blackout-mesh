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
  generated_at: string;
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
