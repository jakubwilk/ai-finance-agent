'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import {
  apiClient,
  type CashflowSummary,
  type GraphStructureResponse,
  type RunHistoryEntry,
} from '@/modules/common/api';
import { GraphView } from '@/modules/common/components/GraphView';
import { CashflowSummaryPanel } from '@/modules/runs/components/CashflowSummaryPanel';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; history: RunHistoryEntry[]; graph: GraphStructureResponse };

// Cashflow summary loads independently — a failure here (or the endpoint
// simply not existing on a real backend yet, see
// ApiClient.getCashflowSummary's doc comment) must never block the
// checkpoint timeline/graph above, which is the page's core feature.
type CashflowLoadState =
  { status: 'loading' } | { status: 'error' } | { status: 'success'; summary: CashflowSummary };

export interface RunDetailPageProps {
  threadId: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

export function RunDetailPage({ threadId }: RunDetailPageProps) {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const [cashflowState, setCashflowState] = useState<CashflowLoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    apiClient
      .getCashflowSummary(threadId)
      .then((summary) => {
        if (!cancelled) setCashflowState({ status: 'success', summary });
      })
      .catch(() => {
        if (!cancelled) setCashflowState({ status: 'error' });
      });

    return () => {
      cancelled = true;
    };
  }, [threadId]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([apiClient.getRunHistory(threadId), apiClient.getGraphStructure()])
      .then(([history, graph]) => {
        if (cancelled) return;
        // get_state_history returns checkpoints most-recent-first; sort
        // explicitly rather than trusting array order (see docs/13's
        // provisional /runs/{thread_id}/history contract).
        const sorted = [...history].sort((a, b) => a.step - b.step);
        setState({ status: 'success', history: sorted, graph });
        setSelectedStep(sorted.at(-1)?.step ?? null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load run history',
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [threadId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
      <Link
        href="/runs"
        className="mb-2 w-fit text-sm text-primary underline-offset-4 hover:underline"
      >
        ← Back to runs
      </Link>
      <h1 className="mb-4 font-mono text-lg font-semibold">{threadId}</h1>

      {state.status === 'loading' && (
        <p className="text-sm text-muted-foreground" role="status">
          Loading run history…
        </p>
      )}
      {state.status === 'error' && (
        <p className="text-sm text-destructive" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'success' && (
        <RunDetailContent
          history={state.history}
          graph={state.graph}
          selectedStep={selectedStep}
          onSelectStep={setSelectedStep}
        />
      )}

      {cashflowState.status === 'success' && (
        <div className="mt-6 border-t border-border pt-4">
          <CashflowSummaryPanel summary={cashflowState.summary} />
        </div>
      )}
    </div>
  );
}

interface RunDetailContentProps {
  history: RunHistoryEntry[];
  graph: GraphStructureResponse;
  selectedStep: number | null;
  onSelectStep: (step: number) => void;
}

function RunDetailContent({ history, graph, selectedStep, onSelectStep }: RunDetailContentProps) {
  const selected = history.find((entry) => entry.step === selectedStep) ?? null;

  return (
    <div className="grid h-[480px] shrink-0 grid-cols-[minmax(200px,240px)_1fr_minmax(240px,320px)] gap-4">
      <ol className="flex flex-col gap-1 overflow-y-auto" aria-label="Checkpoint timeline">
        {history.map((entry) => (
          <li key={entry.checkpointId}>
            <button
              type="button"
              onClick={() => onSelectStep(entry.step)}
              aria-current={entry.step === selectedStep}
              className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                entry.step === selectedStep ? 'border-primary bg-primary/5' : 'border-border'
              }`}
            >
              <div className="font-medium">Step {entry.step}</div>
              <div className="text-xs text-muted-foreground">{formatDate(entry.createdAt)}</div>
            </button>
          </li>
        ))}
      </ol>

      <div className="min-h-0">
        <GraphView nodes={graph.nodes} edges={graph.edges} activeNodeIds={selected?.next} />
      </div>

      <div className="overflow-y-auto rounded-md border border-border p-3">
        <h2 className="mb-2 text-sm font-semibold">State at step {selected?.step}</h2>
        <p className="mb-2 text-xs text-muted-foreground">
          {selected && selected.next.length > 0
            ? `Next: ${selected.next.join(', ')}`
            : 'End of run (no next node)'}
        </p>
        <pre className="overflow-x-auto rounded bg-muted p-2 text-xs">
          {JSON.stringify(selected?.values ?? {}, null, 2)}
        </pre>
      </div>
    </div>
  );
}
