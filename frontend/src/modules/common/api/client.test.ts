import { afterEach, describe, expect, it, vi } from 'vitest';

import { client } from '@/modules/common/api/client';
import { ApiError } from '@/modules/common/models/api';

function mockFetchOnce(body: unknown, init?: { ok?: boolean; status?: number }) {
  const ok = init?.ok ?? true;
  const status = init?.status ?? 200;
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('client', () => {
  it('GET /graph/structure', async () => {
    const fetchMock = mockFetchOnce({ mermaid: 'flowchart TD' });
    const result = await client.getGraphStructure();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backend/graph/structure',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    );
    expect(result).toEqual({ mermaid: 'flowchart TD' });
  });

  it('GET /runs', async () => {
    const fetchMock = mockFetchOnce([]);
    await client.listRuns();
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/runs', expect.anything());
  });

  it('POST /runs', async () => {
    const fetchMock = mockFetchOnce({ threadId: 't1', status: 'running' });
    await client.triggerRun();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backend/runs',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('GET /runs/{thread_id}/state', async () => {
    const fetchMock = mockFetchOnce({ values: {}, pendingReviews: [] });
    await client.getRunState('abc');
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/runs/abc/state', expect.anything());
  });

  it('GET /categories', async () => {
    const fetchMock = mockFetchOnce([]);
    await client.getCategories();
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/categories', expect.anything());
  });

  it('GET /runs/{thread_id}/history', async () => {
    const fetchMock = mockFetchOnce([]);
    await client.getRunHistory('abc');
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/runs/abc/history', expect.anything());
  });

  it('POST /runs/{thread_id}/resume with the resume payload', async () => {
    const fetchMock = mockFetchOnce({});
    await client.resumeRun('abc', { category: 'groceries' });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backend/runs/abc/resume',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ resume: { category: 'groceries' } }),
      }),
    );
  });

  it('GET /runs/{thread_id}/cashflow', async () => {
    const fetchMock = mockFetchOnce({
      statementId: null,
      weekly: null,
      rollingMonth: null,
      fixedCostsStatus: [],
    });
    await client.getCashflowSummary('abc');
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/runs/abc/cashflow', expect.anything());
  });

  it('DELETE /runs/{thread_id}', async () => {
    const fetchMock = mockFetchOnce(undefined, { status: 204 });
    await client.deleteRun('abc');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backend/runs/abc',
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('GET /health', async () => {
    const fetchMock = mockFetchOnce({ status: 'ok', database: true, ollama: true });
    await client.getHealth();
    expect(fetchMock).toHaveBeenCalledWith('/api/backend/health', expect.anything());
  });

  it('throws ApiError on a non-2xx response', async () => {
    mockFetchOnce({ detail: 'not found' }, { ok: false, status: 404 });
    await expect(client.getRunState('missing')).rejects.toBeInstanceOf(ApiError);
  });
});
