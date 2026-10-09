import { components } from './schema';

export type ScopeTotals = components["schemas"]["ScopeTotals"];
export type RunIdentity = components["schemas"]["RunIdentity"];
export type CrossRouteContract = components["schemas"]["CrossRouteContract"];
export type SourceInfo = components["schemas"]["SourceInfo"];
export type FeederLimits = Record<string, number>;
export type Service = components["schemas"]["ServiceSnapshot"];
export type HospitalRoom = components["schemas"]["HospitalRoom"];
export type HospitalZone = components["schemas"]["HospitalZone"];
export type ClassroomInfo = components["schemas"]["ClassroomInfo"];
export type ClassroomZone = components["schemas"]["ClassroomZone"];
export type FacilityZones = components["schemas"]["FacilityZones"];
export type SystemEvent = components["schemas"]["SystemEvent"];

export type ActivityState = components["schemas"]["ActivitySnapshot"]["state"];
export type ActivityPrediction = components["schemas"]["ActivitySnapshot"];
export type ModelStatus = components["schemas"]["ModelStatusResponse"];
export type ReplayStatus = components["schemas"]["ReplaySnapshot"];
export type AllocationStatus = components["schemas"]["AllocationSnapshot"];
export type ActivityObservation = components["schemas"]["ActivityObservationRequest"];

export type Snapshot = components["schemas"]["SystemSnapshot"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type RfidScanResponse = components["schemas"]["RfidScanResponse"];
export type CapacityChangeResponse = components["schemas"]["CapacityChangeResponse"];
export type ClassroomLoadResponse = components["schemas"]["ClassroomLoadResponse"];
export type FeederChangeResponse = components["schemas"]["FeederChangeResponse"];

export type ClassroomDemoLoad = components["schemas"]["ClassroomDemoLoad"];
export type ClassroomDemoRoom = components["schemas"]["ClassroomDemoRoom"];
export type ClassroomDemoSnapshot = components["schemas"]["ClassroomDemoSnapshot"];

export type HospitalDemoScenario = "normal" | "overload" | "cooling_failure" | "upstream_loss" | "missing_sensor";
export type Hypothesis = components["schemas"]["Hypothesis"];
export type HospitalDemoDiagnosis = components["schemas"]["HospitalDemoDiagnosis"];
export type HospitalDemoTransformer = components["schemas"]["HospitalDemoTransformer"];
export type HospitalDemoSnapshot = components["schemas"]["HospitalDemoSnapshot"];

export type WebSocketEnvelope = components["schemas"]["WebSocketMessageEnvelope"];
