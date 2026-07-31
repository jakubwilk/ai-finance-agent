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
 * One `CATEGORIES` row (docs/01-spec-data-model.md).
 */
export interface Category {
  id: string;
  name: string;
  score: number;
  type: 'income' | 'expense' | 'transfer';
}

/**
 * One entry of the categorization subgraph's `human_review` interrupt
 * payload (`{"pending_reviews": [...]}`, see
 * backend/src/finance_agent/subgraphs/categorization/nodes.py
 * `make_human_review`) — a transaction whose LLM classification fell
 * below the confidence threshold and needs a human decision.
 */
export interface PendingReview {
  transactionId: string;
  description: string;
  counterparty: string | null;
  amount: string;
  suggestedCategory: string | null;
  suggestedConfidence: number | null;
}

/**
 * Graph state for a thread (GET /runs/{thread_id}/state). Mirrors
 * LangGraph's `StateSnapshot` (langgraph.types), which keeps channel
 * `values` and pending `interrupts` as separate fields rather than one
 * merged dict. `values` stays loosely typed because the backend's
 * MasterGraphState is still a placeholder skeleton
 * (backend/src/finance_agent/graph/state.py) with no domain fields
 * defined yet; `pendingReviews` decodes the one interrupt shape that's
 * actually defined today (categorization's `human_review`) — reconcile
 * once other subgraphs add their own `interrupt()` calls.
 */
export interface RunState {
  values: Record<string, unknown>;
  pendingReviews: PendingReview[];
}

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

/**
 * One entry of `PeriodSummary.category_breakdown` (docs/07-spec-cashflow-calculation.md,
 * backend/src/finance_agent/subgraphs/cashflow/state.py `CategoryBreakdownEntry`).
 * `total` is signed — positive for income categories, negative for
 * expense categories, since `breakdown_by_category` groups every
 * transaction in the period, not just expenses. `categoryId: null` means
 * "Nieskategoryzowane" (uncategorized).
 */
export interface CategoryBreakdownEntry {
  categoryId: string | null;
  categoryName: string;
  total: string;
}

/**
 * Reconciliation status for one `FIXED_COSTS` row against the current
 * statement's transactions (docs/05-spec-fixed-costs.md,
 * `subgraphs/cashflow/state.py` `FixedCostStatusEntry`).
 */
export interface FixedCostStatusEntry {
  fixedCostId: string;
  fixedCostName: string;
  expectedAmount: string;
  actualAmount: string | null;
  status: 'matched' | 'amount_changed' | 'missing_payment';
}

/**
 * One period's aggregation (docs/07-spec-cashflow-calculation.md,
 * `subgraphs/cashflow/state.py` `PeriodSummary`). `totalExpense`/`surplus`
 * are signed decimal strings (expense negative).
 */
export interface PeriodSummary {
  periodStart: string;
  periodEnd: string;
  totalIncome: string;
  totalExpense: string;
  categoryBreakdown: CategoryBreakdownEntry[];
  needsReviewCount: number;
  surplus: string;
}

/**
 * Output of the `cashflow_calculation` subgraph
 * (`backend/src/finance_agent/subgraphs/cashflow/state.py` `CashflowState`).
 * `weekly` covers the current statement's own period; `rollingMonth`
 * covers the calendar month to date across every processed statement in
 * it — there is no multi-week time series anywhere in the real contract,
 * so "trend" here means comparing these two periods, not a history array.
 */
export interface CashflowSummary {
  statementId: string | null;
  weekly: PeriodSummary | null;
  rollingMonth: PeriodSummary | null;
  fixedCostsStatus: FixedCostStatusEntry[];
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
   * Not in docs/13-spec-backend-api.md's endpoint table — a frontend-only
   * convenience so Review Queue can render a category dropdown against
   * something other than free text (see docs/06-spec-categorization.md's
   * `human_review`, which matches decisions by exact category name).
   * Whether/how a real `GET /categories` gets added to the backend is a
   * separate call for that side of the project, not decided here.
   */
  getCategories(): Promise<Category[]>;
  /**
   * GET /runs/{thread_id}/cashflow. `graph/master.py`'s
   * `_cashflow_calculation_node` persists the `cashflow_calculation`
   * subgraph's result into `CashflowSummary` (`db/models.py`), keyed by
   * `thread_id` — the subgraph itself is stateless per invocation, so this
   * table is the only place its output survives past that node returning.
   */
  getCashflowSummary(threadId: string): Promise<CashflowSummary>;
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
  /**
   * DELETE /runs/{thread_id} — not yet implemented by the backend, see
   * docs/13-spec-backend-api.md. Removes a run's tracking row entirely;
   * irreversible.
   */
  deleteRun(threadId: string): Promise<void>;
  getHealth(): Promise<HealthResponse>;
}
