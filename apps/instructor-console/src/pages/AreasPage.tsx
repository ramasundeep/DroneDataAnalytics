import { api } from '../api/client';
import type { Area, Bounds } from '../api/types';
import { useApi } from '../api/useApi';
import { ResourceTable, type Column } from '../components/ResourceTable';

function formatBounds(b: Bounds): string {
  const f = (n: number) => n.toFixed(4);
  return `${f(b.min_lat)}, ${f(b.min_lon)} → ${f(b.max_lat)}, ${f(b.max_lon)}`;
}

const columns: Column<Area>[] = [
  { header: 'ID', cell: (a) => <code>{a.id}</code> },
  { header: 'Name', cell: (a) => a.name },
  { header: 'Version', cell: (a) => a.version },
  { header: 'Classification', cell: (a) => a.classification },
  { header: 'Landing pads', cell: (a) => a.landing_pads },
  {
    header: 'Bounds (lat, lon)',
    cell: (a) => <span className="mono">{formatBounds(a.bounds)}</span>,
  },
];

export function AreasPage() {
  const state = useApi(api.areas);
  return (
    <ResourceTable
      title="Areas"
      description="Areas of operations (area package manifests) known to the API."
      state={state}
      columns={columns}
      rowKey={(a) => a.id}
      emptyText="No areas are registered."
    />
  );
}
