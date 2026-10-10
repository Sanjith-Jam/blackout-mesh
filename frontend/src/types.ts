import type { components } from './schema';

export type CityDemoSnapshot = components['schemas']['CityDemoResponse'];
export type DemandForecast = components['schemas']['DemandForecastResponse'];
export type DemoEvidence = components['schemas']['DemoEvidence'];

export type SourceInfo = components['schemas']['SourceInfo'];
export type Service = components['schemas']['ServiceSnapshot'];
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
export type HospitalDemoScenario = components['schemas']['HospitalDemoAction']['scenario'];
export type HospitalFaultSnapshot = components['schemas']['HospitalDemoResponse'];
export type DiagnosticHypothesis = components['schemas']['HospitalDiagnosisResponse']['hypotheses'][number];
export type DiagnosticAbstention = components['schemas']['HospitalDiagnosisResponse']['abstention'];
export type HospitalDemoDiagnosis = components['schemas']['HospitalDiagnosisResponse'];
export type HospitalDemoActionName = NonNullable<components['schemas']['HospitalDemoAction']['action']>;
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
export type HistoryPage = components['schemas']['HistoryPageResponse'];
export type HistoryRuns = components['schemas']['HistoryRunsResponse'];
export type WebSocketEnvelope = components['schemas']['WebSocketMessageEnvelope'];
