import {
  MOCK_GRAPH_STRUCTURE,
  MOCK_HEALTH,
  MOCK_RUNS,
  MOCK_RUN_HISTORY,
  MOCK_RUN_STATE,
} from '@/modules/common/api/fixtures';
import type { ApiClient, RunSummary } from '@/modules/common/models/api';

const MOCK_DELAY_MS = 300;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS));
}

// Mutable so triggerRun() has somewhere to persist a new run and
// listRuns() can reflect it — mirrors how the real backend will behave
// (POST /runs followed by GET /runs shows the new run) without waiting
// on Plan A step 13.
let runsState: RunSummary[] = [...MOCK_RUNS];

/** Test-only: restores runsState so trigger tests don't leak between tests. */
export function resetMockRuns() {
  runsState = [...MOCK_RUNS];
}

export const mockClient: ApiClient = {
  getGraphStructure() {
    return delay(MOCK_GRAPH_STRUCTURE);
  },

  listRuns() {
    return delay([...runsState]);
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
    return delay(MOCK_RUN_STATE);
  },

  getRunHistory() {
    return delay(MOCK_RUN_HISTORY);
  },

  resumeRun() {
    return delay(MOCK_RUN_STATE);
  },

  getHealth() {
    return delay(MOCK_HEALTH);
  },
};
