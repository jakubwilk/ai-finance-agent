import {
  ApiError,
  type ApiClient,
  type CashflowSummary,
  type Category,
  type GraphStructureResponse,
  type HealthResponse,
  type RunHistoryEntry,
  type RunState,
  type RunSummary,
} from '@/modules/common/models/api';

// Relative — same-origin, routed through app/api/backend/[...path]/route.ts,
// which is the only place `BACKEND_API_KEY` (docs/13's `require_api_key`)
// gets attached. Keeping it out of this file means the browser bundle
// never contains the key the way a `NEXT_PUBLIC_` variable would.
const BASE_URL = '/api/backend';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `${init?.method ?? 'GET'} ${path} failed: ${response.status}`,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const client: ApiClient = {
  getGraphStructure() {
    return request<GraphStructureResponse>('/graph/structure');
  },

  listRuns() {
    return request<RunSummary[]>('/runs');
  },

  getCategories() {
    return request<Category[]>('/categories');
  },

  getCashflowSummary(threadId) {
    return request<CashflowSummary>(`/runs/${threadId}/cashflow`);
  },

  triggerRun() {
    return request<RunSummary>('/runs', { method: 'POST' });
  },

  getRunState(threadId) {
    return request<RunState>(`/runs/${threadId}/state`);
  },

  getRunHistory(threadId) {
    return request<RunHistoryEntry[]>(`/runs/${threadId}/history`);
  },

  resumeRun(threadId, resumeValue) {
    return request<RunState>(`/runs/${threadId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ resume: resumeValue }),
    });
  },

  deleteRun(threadId) {
    return request<void>(`/runs/${threadId}`, { method: 'DELETE' });
  },

  getHealth() {
    return request<HealthResponse>('/health');
  },
};
