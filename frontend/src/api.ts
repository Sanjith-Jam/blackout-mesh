import { 
  Snapshot, 
  HealthResponse, 
  RfidScanResponse, 
  CapacityChangeResponse, 
  ClassroomLoadResponse, 
  FeederChangeResponse,
  ModelStatus
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function getWebSocketUrl(path = '/ws/live'): string {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = path;
  url.search = '';
  return url.toString();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(response.status, `HTTP error ${response.status}`);
    }

    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error('Network or connection error. Backend may be unavailable.');
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return fetchJson<HealthResponse>('/api/v1/health', { signal });
}

export async function fetchSnapshot(signal?: AbortSignal): Promise<Snapshot> {
  return fetchJson<Snapshot>('/api/v1/snapshot', { signal });
}

export async function fetchModelStatus(signal?: AbortSignal): Promise<ModelStatus> {
  return fetchJson<ModelStatus>('/api/v1/model/status', { signal });
}

export async function setReplayAction(action: 'start' | 'pause' | 'reset'): Promise<void> {
  await fetchJson('/api/v1/replay', { method: 'POST', body: JSON.stringify({ action }) });
}

export async function processRfidScan(uid: string): Promise<RfidScanResponse> {
  return fetchJson<RfidScanResponse>('/api/v1/rfid/scan', {
    method: 'POST',
    body: JSON.stringify({ uid })
  });
}

export async function changeCapacity(capacity_w: number): Promise<CapacityChangeResponse> {
  return fetchJson<CapacityChangeResponse>('/api/v1/simulation/capacity', {
    method: 'POST',
    body: JSON.stringify({ capacity_w })
  });
}

export async function changeClassroomLoad(classroom_id: string, active: boolean): Promise<ClassroomLoadResponse> {
  return fetchJson<ClassroomLoadResponse>('/api/v1/simulation/classroom-load', {
    method: 'POST',
    body: JSON.stringify({ classroom_id, active })
  });
}

export async function changeFeeder(feeder: string, available: boolean): Promise<FeederChangeResponse> {
  return fetchJson<FeederChangeResponse>('/api/v1/simulation/feeder', {
    method: 'POST',
    body: JSON.stringify({ feeder, available })
  });
}
