'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiClient, type Category, type PendingReview } from '@/modules/common/api';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; pendingReviews: PendingReview[]; categories: Category[] };

export interface ReviewQueuePageProps {
  threadId: string;
}

function formatConfidence(confidence: number | null) {
  return confidence === null ? '—' : `${Math.round(confidence * 100)}%`;
}

export function ReviewQueuePage({ threadId }: ReviewQueuePageProps) {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([apiClient.getRunState(threadId), apiClient.getCategories()])
      .then(([runState, categories]) => {
        if (cancelled) return;
        setState({ status: 'success', pendingReviews: runState.pendingReviews, categories });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : 'Failed to load review queue',
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [threadId]);

  const handleSubmit = () => {
    setSubmitting(true);
    setSubmitError(null);

    apiClient
      .resumeRun(threadId, { decisions })
      .then((runState) => {
        setState((prev) =>
          prev.status === 'success' ? { ...prev, pendingReviews: runState.pendingReviews } : prev,
        );
        setDecisions({});
      })
      .catch((error: unknown) => {
        setSubmitError(error instanceof Error ? error.message : 'Failed to submit decisions');
      })
      .finally(() => {
        setSubmitting(false);
      });
  };

  const decisionCount = Object.keys(decisions).length;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 p-4">
      <div className="flex flex-col gap-1">
        <Link
          href={`/runs/${threadId}`}
          className="w-fit text-sm text-primary underline-offset-4 hover:underline"
        >
          ← Back to run
        </Link>
        <Link
          href="/runs"
          className="w-fit text-sm text-primary underline-offset-4 hover:underline"
        >
          ← Back to runs
        </Link>
      </div>
      <h1 className="font-mono text-lg font-semibold">Review queue — {threadId}</h1>

      {state.status === 'loading' && (
        <p className="text-sm text-muted-foreground" role="status">
          Loading review queue…
        </p>
      )}
      {state.status === 'error' && (
        <p className="text-sm text-destructive" role="alert">
          {state.message}
        </p>
      )}
      {state.status === 'success' && state.pendingReviews.length === 0 && (
        <p className="text-sm text-muted-foreground">All reviews resolved.</p>
      )}
      {state.status === 'success' && state.pendingReviews.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead>Counterparty</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Suggested</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Category</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {state.pendingReviews.map((review) => (
                <TableRow key={review.transactionId}>
                  <TableCell>{review.description}</TableCell>
                  <TableCell>{review.counterparty ?? '—'}</TableCell>
                  <TableCell>{review.amount}</TableCell>
                  <TableCell>{review.suggestedCategory ?? '—'}</TableCell>
                  <TableCell>{formatConfidence(review.suggestedConfidence)}</TableCell>
                  <TableCell>
                    <Select
                      value={decisions[review.transactionId] ?? null}
                      onValueChange={(value) => {
                        setDecisions((prev) => ({
                          ...prev,
                          [review.transactionId]: value as string,
                        }));
                      }}
                    >
                      <SelectTrigger aria-label={`Category for ${review.description}`}>
                        <SelectValue placeholder="Choose category" />
                      </SelectTrigger>
                      <SelectContent>
                        {state.categories.map((category) => (
                          <SelectItem key={category.id} value={category.name}>
                            {category.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center gap-2">
            <Button onClick={handleSubmit} disabled={submitting || decisionCount === 0}>
              {submitting ? 'Submitting…' : `Submit decisions (${decisionCount})`}
            </Button>
            {submitError && (
              <p className="text-xs text-destructive" role="alert">
                {submitError}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
