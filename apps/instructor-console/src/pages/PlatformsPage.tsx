import { api } from '../api/client';
import type { Platform } from '../api/types';
import { useApi } from '../api/useApi';
import { ResourceTable, type Column } from '../components/ResourceTable';

const columns: Column<Platform>[] = [
  { header: 'ID', cell: (p) => <code>{p.id}</code> },
  { header: 'Name', cell: (p) => p.name },
  { header: 'Class', cell: (p) => p.class },
  { header: 'Status', cell: (p) => p.status },
  { header: 'Version', cell: (p) => p.version },
];

export function PlatformsPage() {
  const state = useApi(api.platforms);
  return (
    <ResourceTable
      title="Platforms"
      description="Vehicle platforms registered with the API (from platforms/<id>/platform.yaml)."
      state={state}
      columns={columns}
      rowKey={(p) => p.id}
      emptyText="No platforms are registered."
    />
  );
}
