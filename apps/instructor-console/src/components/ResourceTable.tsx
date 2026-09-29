import type { ReactNode } from 'react';
import type { LoadState } from '../api/useApi';

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
}

interface Props<T> {
  title: string;
  description: string;
  state: LoadState<T[]>;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  emptyText: string;
}

export function ResourceTable<T>({
  title,
  description,
  state,
  columns,
  rowKey,
  emptyText,
}: Props<T>) {
  return (
    <section>
      <h1>{title}</h1>
      <p className="muted">{description}</p>
      {state.kind === 'loading' && <p role="status">Loading…</p>}
      {state.kind === 'error' && (
        <div className="banner banner--error" role="alert">
          Could not load {title.toLowerCase()} from the API: {state.message}
        </div>
      )}
      {state.kind === 'ok' && state.data.length === 0 && <p className="muted">{emptyText}</p>}
      {state.kind === 'ok' && state.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.header} scope="col">
                    {c.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.data.map((row) => (
                <tr key={rowKey(row)}>
                  {columns.map((c) => (
                    <td key={c.header}>{c.cell(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
