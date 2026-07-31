import {
  MOCK_CASHFLOW_SUMMARY,
  MOCK_CATEGORIES,
  MOCK_GRAPH_STRUCTURE,
  MOCK_HEALTH,
  MOCK_RUNS,
  MOCK_RUN_HISTORY,
  MOCK_RUN_STATE,
} from '@/modules/common/api/fixtures';
import type { ApiClient, RunState, RunSummary } from '@/modules/common/models/api';

const MOCK_DELAY_MS = 300;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS));
}

// Mutable so triggerRun() has somewhere to persist a new run and
// listRuns() can reflect it — mirrors how the real backend will behave
// (POST /runs followed by GET /runs shows the new run) without waiting
// on Plan A step 13.
let runsState: RunSummary[] = [...MOCK_RUNS];

// Mutable so resumeRun() can remove resolved pending reviews — mirrors the
// real `human_review` interrupt: a decision for a transaction resolves it,
// no decision leaves it `needs_review` (docs/06-spec-categorization.md).
let reviewState: RunState = {
  values: { ...MOCK_RUN_STATE.values },
  pendingReviews: [...MOCK_RUN_STATE.pendingReviews],
};

/** Test-only: restores runsState/reviewState so tests don't leak into each other. */
export function resetMockRuns() {
  runsState = [...MOCK_RUNS];
  reviewState = {
    values: { ...MOCK_RUN_STATE.values },
    pendingReviews: [...MOCK_RUN_STATE.pendingReviews],
  };
}

function isDecisionsPayload(value: unknown): value is { decisions: Record<string, string> } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'decisions' in value &&
    typeof (value as { decisions: unknown }).decisions === 'object'
  );
}

export const mockClient: ApiClient = {
  getGraphStructure() {
    return delay(MOCK_GRAPH_STRUCTURE);
  },

  listRuns() {
    return delay([...runsState]);
  },

  getCategories() {
    return delay([...MOCK_CATEGORIES]);
  },

  getCashflowSummary() {
    return delay(MOCK_CASHFLOW_SUMMARY);
  },

  triggerRun() {
    const newRun: RunSummary = {
      threadId: `manual-${Date.now()}`,
      status: 'running',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    runsState = [newRun, ...runsState];
    return delay(newRun);
  },

  getRunState() {
    return delay({
      values: { ...reviewState.values },
      pendingReviews: [...reviewState.pendingReviews],
    });
  },

  getRunHistory() {
    return delay(MOCK_RUN_HISTORY);
  },

  resumeRun(threadId, resumeValue) {
    const decisions = isDecisionsPayload(resumeValue) ? resumeValue.decisions : {};
    reviewState = {
      ...reviewState,
      pendingReviews: reviewState.pendingReviews.filter(
        (review) => decisions[review.transactionId] === undefined,
      ),
    };

    if (reviewState.pendingReviews.length === 0) {
      runsState = runsState.map((run) =>
        run.threadId === threadId && run.status === 'waiting_for_review'
          ? { ...run, status: 'completed', updatedAt: new Date().toISOString() }
          : run,
      );
    }

    return delay({
      values: { ...reviewState.values },
      pendingReviews: [...reviewState.pendingReviews],
    });
  },

  deleteRun(threadId) {
    runsState = runsState.filter((run) => run.threadId !== threadId);
    return delay(undefined);
  },

  getHealth() {
    return delay(MOCK_HEALTH);
  },
};
