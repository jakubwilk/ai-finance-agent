import {
  ApiError,
  type ApiClient,
  type GraphStructureResponse,
  type HealthResponse,
  type RunHistoryEntry,
  type RunState,
  type RunSummary,
} from '@/modules/common/models/api';

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? 'http://localhost:8000';

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

  return (await response.json()) as T;
}

export const client: ApiClient = {
  getGraphStructure() {
    return request<GraphStructureResponse>('/graph/structure');
  },

  listRuns() {
    return request<RunSummary[]>('/runs');
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

  getHealth() {
    return request<HealthResponse>('/health');
  },
};
