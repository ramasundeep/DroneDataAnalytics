// Types for the CD Sim API responses consumed by the console (Phase 0).
// Keep these in step with the FastAPI models in services/api.

export type ServiceStatus = 'ok' | 'degraded' | 'unreachable';
export type OverallStatus = 'ok' | 'degraded';

export interface ServiceHealth {
  name: string;
  url: string;
  status: ServiceStatus;
  detail: string;
  latency_ms: number | null;
}

export interface SystemHealth {
  status: OverallStatus;
  services: ServiceHealth[];
}

export interface Platform {
  id: string;
  name: string;
  class: string;
  status: string;
  version: string;
}

export interface Bounds {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface Area {
  id: string;
  name: string;
  version: string;
  classification: string;
  landing_pads: number;
  bounds: Bounds;
}

export interface Scenario {
  id: string;
  name: string;
  session_kind: string;
  area_id: string;
  rubric_id: string;
}
