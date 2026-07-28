/**
 * Types mirroring the endpoint table in docs/13-spec-backend-api.md.
 * Some shapes are provisional (see inline notes) because the FastAPI
 * backend (Plan A step 13) doesn't exist yet — reconcile once it does.
 */

export type RunStatus = 'running' | 'completed' | 'failed' | 'waiting_for_review';

export interface RunSummary {
  threadId: string;
  status: RunStatus;
  createdAt: string;
  updatedAt: string;
}

/**
 * Raw graph state for a thread (GET /runs/{thread_id}/state). Loosely
 * typed because the backend's MasterGraphState is still a placeholder
 * skeleton (backend/src/finance_agent/graph/state.py) with no domain
 * fields defined yet.
 */
export type RunState = Record<string, unknown>;

/**
 * One entry of get_state_history (GET /runs/{thread_id}/history).
 * Mirrors LangGraph's StateSnapshot shape (langgraph-persistence skill)
 * but the exact JSON the backend will serialize isn't decided yet.
 */
export interface RunHistoryEntry {
  checkpointId: string;
  step: number;
  values: Record<string, unknown>;
  next: string[];
  createdAt: string;
}

export interface GraphNode {
  id: string;
  label: string;
  /** Visual hint for special node roles from the mermaid shapes in docs/11 (`[[alert]]`, `{{interrupt}}`). */
  kind?: 'default' | 'interrupt' | 'alert';
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface GraphStructureResponse {
  mermaid: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down';
  database: boolean;
  ollama: boolean;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * One function per endpoint in docs/13-spec-backend-api.md. Implemented
 * by both api/client.ts (real backend) and api/mockClient.ts (fixtures)
 * so the two can never drift in signature.
 */
export interface ApiClient {
  getGraphStructure(): Promise<GraphStructureResponse>;
  listRuns(): Promise<RunSummary[]>;
  /**
   * POST /runs. Intentionally takes no account-selection parameter —
   * whether a manual trigger targets one account or both is an open
   * question in docs/13-spec-backend-api.md ("Otwarte kwestie"), not
   * something to guess here.
   */
  triggerRun(): Promise<RunSummary>;
  getRunState(threadId: string): Promise<RunState>;
  getRunHistory(threadId: string): Promise<RunHistoryEntry[]>;
  /**
   * POST /runs/{thread_id}/resume. `resumeValue` maps directly to
   * LangGraph's Command(resume=...) — its shape is inherently
   * node-specific (whatever the interrupted node expects), so it can't
   * be typed more precisely at this layer.
   */
  resumeRun(threadId: string, resumeValue: unknown): Promise<RunState>;
  getHealth(): Promise<HealthResponse>;
}
