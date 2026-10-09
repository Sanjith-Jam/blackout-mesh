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

export interface Snapshot {
  control_revision: number;
  generated_at: string;
  source: SourceInfo;
  feeder_limits_w: FeederLimits;
  requested_mask: number;
  modeled_mask: number;
  indicator_mask: number | null;
  hardware_link: string;
  services: Service[];
}

export interface HealthResponse {
  status: string;
}
