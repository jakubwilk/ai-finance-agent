import { NextResponse, type NextRequest } from 'next/server';

/**
 * Same-origin proxy to the FastAPI backend (docs/13-spec-backend-api.md).
 * Every browser fetch in `common/api/client.ts` goes through this route
 * instead of hitting the backend directly, so `BACKEND_API_KEY`
 * (`require_api_key`, backend/src/finance_agent/api/dependencies.py) is
 * only ever read here, server-side — it never ships to the client bundle
 * the way a `NEXT_PUBLIC_` variable would. Pattern follows Next's own
 * "Proxying to a backend" example
 * (node_modules/next/dist/docs/01-app/02-guides/backend-for-frontend.md).
 */

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY;

async function proxy(request: NextRequest, path: string[]): Promise<NextResponse> {
  const targetUrl = `${BACKEND_API_URL}/${path.join('/')}${request.nextUrl.search}`;
  const body =
    request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, {
      method: request.method,
      headers: {
        'Content-Type': 'application/json',
        ...(BACKEND_API_KEY ? { 'X-API-Key': BACKEND_API_KEY } : {}),
      },
      body,
    });
  } catch {
    return NextResponse.json({ detail: 'Backend unreachable' }, { status: 502 });
  }

  // 204/205 are "null body status" responses per the Fetch spec — a
  // Response constructed with one of these statuses must not have a body.
  // NextResponse.json() always serializes a body (even `JSON.stringify(null)`
  // = "null"), which throws for these statuses, so they're handled
  // separately rather than going through the JSON path below.
  if (upstream.status === 204 || upstream.status === 205) {
    return new NextResponse(null, { status: upstream.status });
  }

  // Deliberately not forwarding upstream response headers back to the
  // client (docs' own Security section: "avoid directly passing incoming
  // request headers to the outgoing response") — only the JSON body and
  // status matter to `client.ts`'s callers.
  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}

type RouteParams = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { path } = await params;
  return proxy(request, path);
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { path } = await params;
  return proxy(request, path);
}

export async function DELETE(request: NextRequest, { params }: RouteParams) {
  const { path } = await params;
  return proxy(request, path);
}
