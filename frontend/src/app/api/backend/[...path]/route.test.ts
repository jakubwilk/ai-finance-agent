import { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function mockFetchOnce(body: unknown, init?: { ok?: boolean; status?: number }) {
  const status = init?.status ?? 200;
  const fetchMock = vi.fn().mockResolvedValue({
    ok: init?.ok ?? true,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

/** Re-imports the route module after setting env vars, since BACKEND_API_URL/
 * BACKEND_API_KEY are read once at module load time. */
async function loadRoute() {
  vi.resetModules();
  return import('./route');
}

describe('backend proxy route handler', () => {
  beforeEach(() => {
    process.env.BACKEND_API_URL = 'http://backend.internal:9000';
    process.env.BACKEND_API_KEY = 'test-secret-key';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.BACKEND_API_URL;
    delete process.env.BACKEND_API_KEY;
  });

  it('forwards a GET request to BACKEND_API_URL with the X-API-Key header', async () => {
    const fetchMock = mockFetchOnce([{ id: 'cat-1', name: 'Groceries' }]);
    const { GET } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/categories');
    const response = await GET(request, { params: Promise.resolve({ path: ['categories'] }) });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://backend.internal:9000/categories',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-API-Key': 'test-secret-key',
        }),
      }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ id: 'cat-1', name: 'Groceries' }]);
  });

  it('forwards nested paths and query strings', async () => {
    const fetchMock = mockFetchOnce({});
    const { GET } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/runs/abc/state?foo=bar');
    await GET(request, { params: Promise.resolve({ path: ['runs', 'abc', 'state'] }) });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://backend.internal:9000/runs/abc/state?foo=bar',
      expect.anything(),
    );
  });

  it('forwards a POST body unmodified', async () => {
    const fetchMock = mockFetchOnce({ values: {}, pendingReviews: [] });
    const { POST } = await loadRoute();

    const requestBody = JSON.stringify({ resume: { decisions: { 'txn-1': 'Groceries' } } });
    const request = new NextRequest('http://localhost:3000/api/backend/runs/abc/resume', {
      method: 'POST',
      body: requestBody,
    });
    await POST(request, { params: Promise.resolve({ path: ['runs', 'abc', 'resume'] }) });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://backend.internal:9000/runs/abc/resume',
      expect.objectContaining({ method: 'POST', body: requestBody }),
    );
  });

  it('forwards a DELETE request to BACKEND_API_URL with the X-API-Key header', async () => {
    const fetchMock = mockFetchOnce(null, { status: 204 });
    const { DELETE } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/runs/abc', {
      method: 'DELETE',
    });
    const response = await DELETE(request, {
      params: Promise.resolve({ path: ['runs', 'abc'] }),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://backend.internal:9000/runs/abc',
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ 'X-API-Key': 'test-secret-key' }),
      }),
    );
    expect(response.status).toBe(204);
  });

  it('does not throw when the upstream response is 204 No Content', async () => {
    // A 204 has no body — Response.json()'s always-serialize-a-body
    // behavior would throw a TypeError for this status if not special-cased
    // (verified directly: `Response.json(null, { status: 204 })` throws
    // "Invalid response status code 204").
    mockFetchOnce(null, { status: 204 });
    const { DELETE } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/runs/abc', {
      method: 'DELETE',
    });

    await expect(
      DELETE(request, { params: Promise.resolve({ path: ['runs', 'abc'] }) }),
    ).resolves.not.toThrow();
  });

  it('passes through the upstream status and JSON body on error', async () => {
    const fetchMock = mockFetchOnce(
      { detail: 'Unknown thread_id: abc' },
      { ok: false, status: 404 },
    );
    const { GET } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/runs/abc/state');
    const response = await GET(request, {
      params: Promise.resolve({ path: ['runs', 'abc', 'state'] }),
    });

    expect(fetchMock).toHaveBeenCalled();
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: 'Unknown thread_id: abc' });
  });

  it('returns 502 when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connect ECONNREFUSED')));
    const { GET } = await loadRoute();

    const request = new NextRequest('http://localhost:3000/api/backend/health');
    const response = await GET(request, { params: Promise.resolve({ path: ['health'] }) });

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ detail: 'Backend unreachable' });
  });
});
