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
import { RunStatusBadge } from '@/modules/runs/components/RunStatusBadge';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; runs: RunSummary[] };

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

export function RunsPage() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;

    apiClient
      .listRuns()
      .then((runs) => {
        if (!cancelled) {
          const sorted = [...runs].sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
          );
          setState({ status: 'success', runs: sorted });
        }
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

  return (
    <div className="flex flex-1 flex-col p-4">
      <h1 className="mb-4 text-lg font-semibold">Runs</h1>
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
                  <Link
                    href={`/runs/${run.threadId}`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Details
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
