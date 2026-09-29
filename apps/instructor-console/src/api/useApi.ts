import { useEffect, useState } from 'react';
import { errorMessage } from './client';

export type LoadState<T> =
  { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ok'; data: T };

/** Load a resource once on mount; aborts the request on unmount. */
export function useApi<T>(load: (signal: AbortSignal) => Promise<T>): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ kind: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => setState({ kind: 'ok', data }),
      (err: unknown) => {
        if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(err) });
      },
    );
    return () => controller.abort();
  }, [load]);

  return state;
}
