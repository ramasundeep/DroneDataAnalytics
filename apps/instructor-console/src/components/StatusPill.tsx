import type { ServiceStatus } from '../api/types';

export function StatusPill({ status }: { status: ServiceStatus }) {
  return <span className={`pill pill--${status}`}>{status}</span>;
}
