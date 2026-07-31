'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiClient, type RunSummary } from '@/modules/common/api';
import { DeleteRunButton } from '@/modules/runs/components/DeleteRunButton';
import { RunStatusBadge } from '@/modules/runs/components/RunStatusBadge';
import { TriggerRunButton } from '@/modules/runs/components/TriggerRunButton';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; runs: RunSummary[] };

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

function sortByCreatedAtDesc(runs: RunSummary[]) {
  return [...runs].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
}

export function RunsPage() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    apiClient
      .listRuns()
      .then((runs) => {
        if (!cancelled) setState({ status: 'success', runs: sortByCreatedAtDesc(runs) });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load runs',
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleTriggered = () => {
    apiClient.listRuns().then((runs) => {
      setState({ status: 'success', runs: sortByCreatedAtDesc(runs) });
    });
  };

  const handleDeleted = (threadId: string) => {
    setState((prev) =>
      prev.status === 'success'
        ? { status: 'success', runs: prev.runs.filter((run) => run.threadId !== threadId) }
        : prev,
    );
  };

  return (
    <div className="flex flex-1 flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Runs</h1>
        <TriggerRunButton onTriggered={handleTriggered} />
      </div>
      {state.status === 'loading' && (
        <p className="text-sm text-muted-foreground" role="status">
          Loading runs…
        </p>
      )}
      {state.status === 'error' && (
        <p className="text-sm text-destructive" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'success' && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Thread</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.runs.map((run) => (
              <TableRow key={run.threadId}>
                <TableCell className="font-mono text-xs">{run.threadId}</TableCell>
                <TableCell>
                  <RunStatusBadge status={run.status} />
                </TableCell>
                <TableCell>{formatDate(run.createdAt)}</TableCell>
                <TableCell>{formatDate(run.updatedAt)}</TableCell>
                <TableCell>
                  <div className="flex gap-3">
                    <Link
                      href={`/runs/${run.threadId}`}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      Details
                    </Link>
                    {run.status === 'waiting_for_review' && (
                      <Link
                        href={`/runs/${run.threadId}/review`}
                        className="text-primary underline-offset-4 hover:underline"
                      >
                        Review
                      </Link>
                    )}
                    <DeleteRunButton threadId={run.threadId} onDeleted={handleDeleted} />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
