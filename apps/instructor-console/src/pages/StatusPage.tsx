import { useEffect, useState } from 'react';
import { api, errorMessage } from '../api/client';
import type { ServiceHealth, SystemHealth } from '../api/types';
import { StatusPill } from '../components/StatusPill';

export const POLL_INTERVAL_MS = 5000;

interface PollState {
  health: SystemHealth | null;
  error: string | null;
  lastUpdated: Date | null;
  lastAttempt: Date | null;
}

function formatLatency(ms: number | null | undefined): string {
  return typeof ms === 'number' ? `${ms.toFixed(1)} ms` : '—';
}

function ServiceCard({ service }: { service: ServiceHealth }) {
  return (
    <article className="card" aria-label={`Service ${service.name}`}>
      <div className="card__head">
        <h2 className="card__title">{service.name}</h2>
        <StatusPill status={service.status} />
      </div>
      <dl className="card__meta">
        <dt>Latency</dt>
        <dd>{formatLatency(service.latency_ms)}</dd>
        <dt>URL</dt>
        <dd className="mono">{service.url}</dd>
        <dt>Detail</dt>
        <dd>{service.detail || '—'}</dd>
      </dl>
    </article>
  );
}

export function StatusPage() {
  const [state, setState] = useState<PollState>({
    health: null,
    error: null,
    lastUpdated: null,
    lastAttempt: null,
  });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    const poll = async () => {
      controller = new AbortController();
      try {
        const health = await api.systemHealth(controller.signal);
        if (cancelled) return;
        const now = new Date();
        setState({ health, error: null, lastUpdated: now, lastAttempt: now });
      } catch (err: unknown) {
        if (cancelled) return;
        // Keep the last good snapshot visible but flag that it is stale.
        setState((prev) => ({ ...prev, error: errorMessage(err), lastAttempt: new Date() }));
      }
      if (!cancelled) timer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      controller?.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, []);

  const { health, error, lastUpdated, lastAttempt } = state;

  return (
    <section>
      <h1>System status</h1>
      <p className="muted">
        Health of CD Sim platform services as reported by the API (
        <code>GET /api/v1/system/health</code>), refreshed every {POLL_INTERVAL_MS / 1000} s.
      </p>

      {error && (
        <div className="banner banner--error" role="alert">
          <strong>API unreachable.</strong> The console could not reach the CD Sim API: {error}.
          {health ? ' Showing the last successful snapshot.' : ' Retrying automatically.'}
        </div>
      )}

      {!health && !error && <p role="status">Checking services…</p>}

      {health && (
        <div
          className={`banner banner--${health.status === 'ok' ? 'ok' : 'degraded'}`}
          role="status"
        >
          {health.status === 'ok'
            ? 'All services report ok.'
            : 'One or more services are degraded or unreachable.'}
        </div>
      )}

      {health && health.services.length === 0 && (
        <p className="muted">The API reported no services.</p>
      )}

      {health && health.services.length > 0 && (
        <div className="card-grid">
          {health.services.map((s) => (
            <ServiceCard key={s.name} service={s} />
          ))}
        </div>
      )}

      <p className="muted small">
        Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : 'never'}
        {lastAttempt && lastAttempt !== lastUpdated && (
          <> · last attempt: {lastAttempt.toLocaleTimeString()}</>
        )}
      </p>
    </section>
  );
}
