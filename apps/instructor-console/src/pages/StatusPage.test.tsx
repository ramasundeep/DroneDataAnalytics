import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SystemHealth } from '../api/types';
import { StatusPage } from './StatusPage';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('StatusPage', () => {
  it('renders one card per service from the health endpoint', async () => {
    const health: SystemHealth = {
      status: 'degraded',
      services: [
        {
          name: 'recorder',
          url: 'http://recorder:8001',
          status: 'ok',
          detail: '',
          latency_ms: 12.3,
        },
        {
          name: 'assessment',
          url: 'http://assessment:8002',
          status: 'unreachable',
          detail: 'connection refused',
          latency_ms: null,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(health));
    vi.stubGlobal('fetch', fetchMock);

    render(<StatusPage />);

    expect(await screen.findByRole('article', { name: 'Service recorder' })).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Service assessment' })).toBeInTheDocument();
    expect(screen.getByText('12.3 ms')).toBeInTheDocument();
    expect(screen.getByText('connection refused')).toBeInTheDocument();
    expect(screen.getByText('unreachable')).toHaveClass('pill--unreachable');
    expect(screen.getByText('ok')).toHaveClass('pill--ok');
    expect(screen.getByText(/degraded or unreachable/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/system/health', expect.anything());
  });

  it('shows an error state when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    render(<StatusPage />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('API unreachable');
    expect(alert).toHaveTextContent('Failed to fetch');
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('shows an error state when the API returns an HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'boom' }, 503)));

    render(<StatusPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 503');
  });
});
