import type { components } from './schema';

export type CityDemoSnapshot = components['schemas']['CityDemoResponse'];
export type DemandForecast = components['schemas']['DemandForecastResponse'];
export type DemoEvidence = components['schemas']['DemoEvidence'];

export type SourceInfo = components['schemas']['SourceInfo'];
export type SiteScenarios = components['schemas']['SiteScenariosResponse'];
export type SiteScenarioSwitch = components['schemas']['SiteScenarioResponse'];
export type Service = components['schemas']['ServiceSnapshot'];

/** Modeled watts a service receives; feeder B services can be partly served by the classroom leaves (#33). */
export const servedWatts = (s: Service) => s.served_w ?? (s.modeled_served ? s.watts : 0);
export const serviceStatus = (s: Service) =>
  !s.requested ? 'Not requested' : !s.modeled_served ? 'Shed' : servedWatts(s) < (s.requested_w ?? s.watts) ? 'Partly served' : 'Served';
export type HospitalRoom = components['schemas']['HospitalRoom'];
export type HospitalZone = components['schemas']['HospitalZone'];
export type ClassroomInfo = components['schemas']['ClassroomInfo'];
export type ClassroomZone = components['schemas']['ClassroomZone'];
export type FacilityZones = components['schemas']['FacilityZones'];
export type SystemEvent = components['schemas']['SystemEvent'];
export type ActivityState = components['schemas']['VisualizerActivity']['state'];
export type ActivityPrediction = components['schemas']['ActivitySnapshot'];
export type ModelStatus = components['schemas']['ModelStatusResponse'];
export type ReplayStatus = components['schemas']['ReplaySnapshot'];
export type AllocationExplanation = components['schemas']['AllocationSnapshot']['explanation'];
export type AllocationStatus = components['schemas']['AllocationSnapshot'];
export type ActivityObservation = components['schemas']['ActivityObservationRequest'];
export type Snapshot = components['schemas']['SystemSnapshot'] & { sent_at?: string | null };
export type HealthResponse = components['schemas']['HealthResponse'];
export type RfidScanResponse = components['schemas']['RfidScanResponse'];
export type CapacityChangeResponse = components['schemas']['CapacityChangeResponse'];
export type ClassroomLoadResponse = components['schemas']['ClassroomLoadResponse'];
export type FeederChangeResponse = components['schemas']['FeederChangeResponse'];
export type ClassroomDemoLoad = components['schemas']['VisualizerLoad'];
export type PowerEdgeState = components['schemas']['PowerEdge']['state'];
export type PowerEdge = components['schemas']['PowerEdge'];

export type SiteIdentity = components['schemas']['SiteIdentityResponse'];

export type CommandReceipt = components['schemas']['CommandReceipt'];
export type HardwareStatus = components['schemas']['HardwareStatusResponse'];
export type SafetyStatus = components['schemas']['SafetySnapshot'];
export type ClassroomDemoActivity = components['schemas']['VisualizerActivity'];
export type ClassroomDemoRoom = components['schemas']['ClassroomDemoRoomResponse'];
export type ClassroomDemoActionName = components['schemas']['ClassroomDemoAction']['action'];
export type ClassroomDemoSnapshot = Omit<components['schemas']['ClassroomDemoResponse'], 'hardware'> & {
  hardware?: HardwareStatus | null;
};
export type HospitalDemoScenario = components['schemas']['HospitalDemoAction']['rehearsal'];
export type HospitalFaultSnapshot = components['schemas']['HospitalDemoResponse'];
export type DiagnosticHypothesis = components['schemas']['HospitalDiagnosisResponse']['hypotheses'][number];
export type DiagnosticAbstention = components['schemas']['HospitalDiagnosisResponse']['abstention'];
export type HospitalDemoDiagnosis = components['schemas']['HospitalDiagnosisResponse'];
export type HospitalDemoActionName = NonNullable<components['schemas']['HospitalDemoAction']['action']>;
export type HospitalDemoFault = NonNullable<components['schemas']['HospitalDemoAction']['fault']>;
export type HospitalDemoZone = components['schemas']['HospitalDemoTransformerResponse'];
export type HospitalDemoTransformer = HospitalTransformerView;
type HospitalTransformerView = Omit<components['schemas']['HospitalDemoTransformerResponse'],
  'rated_current_a' | 'activity'> & {
    rated_current_a: number;
    activity: NonNullable<components['schemas']['HospitalDemoTransformerResponse']['activity']>;
  };
export type HospitalDemoSnapshot = Omit<components['schemas']['HospitalDemoResponse'],
  'capacity_w' | 'capacity_range_w' | 'requested_w' | 'served_w' | 'shortfall_w' | 'scanned_zone_ids' |
  'model' | 'replay' | 'transformers'> & {
    capacity_w: number;
    capacity_range_w: [number, number];
    requested_w: number;
    served_w: number;
    shortfall_w: number;
    scanned_zone_ids: string[];
    model: NonNullable<components['schemas']['HospitalDemoResponse']['model']>;
    replay: NonNullable<components['schemas']['HospitalDemoResponse']['replay']>;
    transformers: HospitalTransformerView[];
  };
export type ElectricalStudyInput = components['schemas']['ElectricalInput'];
export type ElectricalStudyResponse = components['schemas']['ElectricalStudyResponse'];
export type HistoryRecord = components['schemas']['HistoryEventRecord'] |
  components['schemas']['HistoryDecisionRecord'] | components['schemas']['HistoryTelemetryRecord'];

export type DistrictActionName = components['schemas']['DistrictActionName'];
export type DistrictActionRequest = components['schemas']['DistrictAction'];
export type DistrictGenerationRequest = components['schemas']['GenerationRequest'];
type DistrictNode = { id: string; role: string; lon: number; lat: number; building_id?: string | null };
type DistrictTopologyEdge = { id: string; from: string; to: string; kind: string };
type DistrictEdgeState = { id: string; closed: boolean; faulted: boolean; energized: boolean; flow_w: number; provenance?: string };
type DistrictLoad = components['schemas']['DistrictLoad'];
type DistrictTransformer = { component_id: string; sensor: Record<string, string | number | boolean | null>; diagnosis: { status: string; suspected_part: string | null; evidence: string[] } };
type DistrictRestoration = { candidate_edge_id?: string | null; applied_edge_id?: string | null; stable_since?: string | null; stable_evidence_count?: number; reason?: string | null; provenance?: string };
type DistrictFault = { component_id: string; kind: string; provenance?: string };
type DistrictState = Omit<components['schemas']['DistrictState'], 'edges' | 'loads' | 'faults' | 'restoration' | 'transformers'> & {
  edges: DistrictEdgeState[]; loads: DistrictLoad[]; faults: DistrictFault[]; restoration: DistrictRestoration; transformers: DistrictTransformer[];
};
type DistrictTopology = Omit<components['schemas']['DistrictTopology'], 'nodes' | 'edges'> & {
  nodes: DistrictNode[]; edges: DistrictTopologyEdge[];
};
type DistrictProfileRow = { hour: number; demand_w: number; pv_w: number; baseline_grid_w: number; dispatch_grid_w: number; battery_soc_wh: number; pv_used_w: number; battery_charge_w: number; battery_discharge_w: number; grid_import_w: number; loss_wh: number };
export type DistrictSnapshot = Omit<components['schemas']['DistrictSnapshot'], 'topology' | 'state' | 'energy'> & {
  topology: DistrictTopology; state: DistrictState;
  energy: Omit<components['schemas']['DistrictEnergy'], 'profile'> & { profile: DistrictProfileRow[] };
};
export type HistoryPage = components['schemas']['HistoryPageResponse'];
export type HistoryRuns = components['schemas']['HistoryRunsResponse'];
export type WebSocketEnvelope = components['schemas']['WebSocketMessageEnvelope'];
