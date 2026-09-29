import { api } from '../api/client';
import type { Scenario } from '../api/types';
import { useApi } from '../api/useApi';
import { ResourceTable, type Column } from '../components/ResourceTable';

const columns: Column<Scenario>[] = [
  { header: 'ID', cell: (s) => <code>{s.id}</code> },
  { header: 'Name', cell: (s) => s.name },
  { header: 'Session kind', cell: (s) => s.session_kind },
  { header: 'Area', cell: (s) => <code>{s.area_id}</code> },
  { header: 'Rubric', cell: (s) => <code>{s.rubric_id}</code> },
];

export function ScenariosPage() {
  const state = useApi(api.scenarios);
  return (
    <ResourceTable
      title="Scenarios"
      description="Scenario definitions (scenarios/*.yaml) known to the API."
      state={state}
      columns={columns}
      rowKey={(s) => s.id}
      emptyText="No scenarios are registered."
    />
  );
}
