'use client';

import { useEffect, useState } from 'react';

import { apiClient, type GraphStructureResponse } from '@/modules/common/api';
import { GraphView } from '@/modules/graph/components/GraphView';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; data: GraphStructureResponse };

export function GraphPage() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    apiClient
      .getGraphStructure()
      .then((data) => {
        if (!cancelled) setState({ status: 'success', data });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load graph structure',
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="border-border border-b px-4 py-3">
        <h1 className="text-lg font-semibold">Master graph</h1>
      </header>
      <div className="min-h-0 flex-1">
        {state.status === 'loading' && (
          <p className="p-4 text-sm text-muted-foreground" role="status">
            Loading graph structure…
          </p>
        )}
        {state.status === 'error' && (
          <p className="p-4 text-sm text-destructive" role="alert">
            {state.message}
          </p>
        )}
        {state.status === 'success' && (
          <GraphView nodes={state.data.nodes} edges={state.data.edges} />
        )}
      </div>
    </div>
  );
}
