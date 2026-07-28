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

export const mockClient: ApiClient = {
  getGraphStructure() {
    return delay(MOCK_GRAPH_STRUCTURE);
  },

  listRuns() {
    return delay(MOCK_RUNS);
  },

  triggerRun() {
    const newRun: RunSummary = {
      threadId: `manual-${Date.now()}`,
      status: 'running',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
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
