// Minimal typed client for the CD Sim API.
//
// All requests go to the relative base path `/api`. The Vite dev server and
// the production nginx both proxy `/api/*` to the API service and strip the
// prefix, so `/api/v1/platforms` reaches the API as `/v1/platforms`.

import type { Area, Platform, Scenario, SystemHealth } from './types';

export const API_BASE = '/api';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  const response = await fetch(url, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(`GET ${url} failed: HTTP ${response.status}`, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  systemHealth: (signal?: AbortSignal) => fetchJson<SystemHealth>('/v1/system/health', { signal }),
  platforms: (signal?: AbortSignal) => fetchJson<Platform[]>('/v1/platforms', { signal }),
  areas: (signal?: AbortSignal) => fetchJson<Area[]>('/v1/areas', { signal }),
  scenarios: (signal?: AbortSignal) => fetchJson<Scenario[]>('/v1/scenarios', { signal }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
