import type {
  Category,
  CashflowSummary,
  GraphEdge,
  GraphNode,
  GraphStructureResponse,
  HealthResponse,
  PendingReview,
  RunHistoryEntry,
  RunState,
  RunSummary,
} from '@/modules/common/models/api';

// Verbatim master graph diagram from docs/11-spec-orchestration-scheduling.md.
const MERMAID = `flowchart TD
    START([start]) --> ING[ingestion subgraph]
    ING --> VER_PRE[verification: pre-check]
    VER_PRE -- ok --> EXT[extraction subgraph]
    VER_PRE -- fail --> ALERT[[alert_immediate]]
    EXT --> VER_POST[verification: post-check sald]
    VER_POST -- ok --> CAT[categorization subgraph]
    VER_POST -- fail --> ALERT
    CAT -- needs_review --> HITL{{interrupt: human review}}
    CAT -- auto --> FIX[fixed_costs_reconciliation]
    HITL --> FIX
    FIX --> CALC[cashflow_calculation]
    CALC --> INV[investment_analysis]
    INV --> REP[reporting]
    REP --> MAIL[email_delivery]
    MAIL --> END([end])`;

// Node/edge ids match the subgraph directory names in backend/src/finance_agent/subgraphs/.
const MOCK_GRAPH_NODES: GraphNode[] = [
  { id: 'start', label: 'start' },
  { id: 'ingestion', label: 'ingestion subgraph' },
  { id: 'verification_pre', label: 'verification: pre-check' },
  { id: 'extraction', label: 'extraction subgraph' },
  { id: 'verification_post', label: 'verification: post-check sald' },
  { id: 'categorization', label: 'categorization subgraph' },
  { id: 'alert_immediate', label: 'alert_immediate', kind: 'alert' },
  { id: 'human_review', label: 'interrupt: human review', kind: 'interrupt' },
  { id: 'fixed_costs_reconciliation', label: 'fixed_costs_reconciliation' },
  { id: 'cashflow_calculation', label: 'cashflow_calculation' },
  { id: 'investment_analysis', label: 'investment_analysis' },
  { id: 'reporting', label: 'reporting' },
  { id: 'email_delivery', label: 'email_delivery' },
  { id: 'end', label: 'end' },
];

const MOCK_GRAPH_EDGES: GraphEdge[] = [
  { id: 'start-ingestion', source: 'start', target: 'ingestion' },
  { id: 'ingestion-verification_pre', source: 'ingestion', target: 'verification_pre' },
  {
    id: 'verification_pre-extraction',
    source: 'verification_pre',
    target: 'extraction',
    label: 'ok',
  },
  {
    id: 'verification_pre-alert_immediate',
    source: 'verification_pre',
    target: 'alert_immediate',
    label: 'fail',
  },
  { id: 'extraction-verification_post', source: 'extraction', target: 'verification_post' },
  {
    id: 'verification_post-categorization',
    source: 'verification_post',
    target: 'categorization',
    label: 'ok',
  },
  {
    id: 'verification_post-alert_immediate',
    source: 'verification_post',
    target: 'alert_immediate',
    label: 'fail',
  },
  {
    id: 'categorization-human_review',
    source: 'categorization',
    target: 'human_review',
    label: 'needs_review',
  },
  {
    id: 'categorization-fixed_costs_reconciliation',
    source: 'categorization',
    target: 'fixed_costs_reconciliation',
    label: 'auto',
  },
  {
    id: 'human_review-fixed_costs_reconciliation',
    source: 'human_review',
    target: 'fixed_costs_reconciliation',
  },
  {
    id: 'fixed_costs_reconciliation-cashflow_calculation',
    source: 'fixed_costs_reconciliation',
    target: 'cashflow_calculation',
  },
  {
    id: 'cashflow_calculation-investment_analysis',
    source: 'cashflow_calculation',
    target: 'investment_analysis',
  },
  { id: 'investment_analysis-reporting', source: 'investment_analysis', target: 'reporting' },
  { id: 'reporting-email_delivery', source: 'reporting', target: 'email_delivery' },
  { id: 'email_delivery-end', source: 'email_delivery', target: 'end' },
];

export const MOCK_GRAPH_STRUCTURE: GraphStructureResponse = {
  mermaid: MERMAID,
  nodes: MOCK_GRAPH_NODES,
  edges: MOCK_GRAPH_EDGES,
};

export const MOCK_RUNS: RunSummary[] = [
  {
    threadId: 'private-2026-W30',
    status: 'completed',
    createdAt: '2026-07-20T06:00:00Z',
    updatedAt: '2026-07-20T06:04:12Z',
  },
  {
    threadId: 'company-2026-W30',
    status: 'waiting_for_review',
    createdAt: '2026-07-20T06:00:00Z',
    updatedAt: '2026-07-20T06:02:47Z',
  },
  {
    threadId: 'private-2026-W29',
    status: 'failed',
    createdAt: '2026-07-13T06:00:00Z',
    updatedAt: '2026-07-13T06:01:03Z',
  },
  {
    threadId: 'company-2026-W29',
    status: 'running',
    createdAt: '2026-07-27T09:15:00Z',
    updatedAt: '2026-07-27T09:15:00Z',
  },
];

// Generic placeholder names, never the user's real data/local/categories.json
// content (see root CLAUDE.md, "Personal financial data: never commit real
// values").
export const MOCK_CATEGORIES: Category[] = [
  { id: 'cat-groceries', name: 'Groceries', score: 90, type: 'expense' },
  { id: 'cat-rent', name: 'Rent', score: 95, type: 'expense' },
  { id: 'cat-subscriptions', name: 'Subscriptions', score: 40, type: 'expense' },
  { id: 'cat-dining', name: 'Dining out', score: 30, type: 'expense' },
  { id: 'cat-salary', name: 'Salary', score: 100, type: 'income' },
  { id: 'cat-transfer', name: 'Transfer', score: 50, type: 'transfer' },
];

// Mirrors the categorization subgraph's `human_review` interrupt payload
// (backend/src/finance_agent/subgraphs/categorization/nodes.py). One entry
// has `suggestedCategory: null` to model the LLM-failure fallback from
// docs/06-spec-categorization.md (confidence 0.0, no category guess).
export const MOCK_PENDING_REVIEWS: PendingReview[] = [
  {
    transactionId: 'txn-1001',
    description: 'Płatność kartą - sklep spożywczy',
    counterparty: 'Sklep Spożywczy Sp. z o.o.',
    amount: '-123.45',
    suggestedCategory: 'Groceries',
    suggestedConfidence: 0.62,
  },
  {
    transactionId: 'txn-1002',
    description: 'Przelew przychodzący',
    counterparty: null,
    amount: '250.00',
    suggestedCategory: null,
    suggestedConfidence: 0.0,
  },
  {
    transactionId: 'txn-1003',
    description: 'Płatność cykliczna - streaming',
    counterparty: 'Streaming Provider',
    amount: '-19.99',
    suggestedCategory: 'Subscriptions',
    suggestedConfidence: 0.71,
  },
];

export const MOCK_RUN_STATE: RunState = {
  values: {
    verification_ok: true,
    needs_review: true,
    visited: ['ingestion', 'verification_pre', 'extraction', 'verification_post', 'categorization'],
  },
  pendingReviews: MOCK_PENDING_REVIEWS,
};

export const MOCK_RUN_HISTORY: RunHistoryEntry[] = [
  {
    checkpointId: 'chk-1',
    step: 0,
    values: {},
    next: ['ingestion'],
    createdAt: '2026-07-20T06:00:00Z',
  },
  {
    checkpointId: 'chk-2',
    step: 1,
    values: { visited: ['ingestion'] },
    next: ['verification_pre'],
    createdAt: '2026-07-20T06:00:41Z',
  },
  {
    checkpointId: 'chk-3',
    step: 2,
    values: { visited: ['ingestion', 'verification_pre'], verification_ok: true },
    next: ['extraction'],
    createdAt: '2026-07-20T06:01:18Z',
  },
];

export const MOCK_HEALTH: HealthResponse = {
  status: 'ok',
  database: true,
  ollama: true,
};

// Mirrors subgraphs/cashflow/state.py's PeriodSummary shape faithfully —
// no real backend endpoint exists for this yet (see
// ApiClient.getCashflowSummary's doc comment), so this fixture is the only
// place the shape is exercised until Plan A adds one. `total` is signed:
// positive entries are income categories, negative are expense, mirroring
// breakdown_by_category grouping every transaction in the period, not just
// expenses. One entry has `categoryId: null` for "Nieskategoryzowane".
const WEEKLY_CATEGORY_BREAKDOWN = [
  { categoryId: 'cat-salary', categoryName: 'Salary', total: '4500.00' },
  { categoryId: 'cat-rent', categoryName: 'Rent', total: '-1800.00' },
  { categoryId: 'cat-groceries', categoryName: 'Groceries', total: '-620.50' },
  { categoryId: 'cat-subscriptions', categoryName: 'Subscriptions', total: '-89.97' },
  { categoryId: null, categoryName: 'Nieskategoryzowane', total: '-45.00' },
];

const ROLLING_MONTH_CATEGORY_BREAKDOWN = [
  { categoryId: 'cat-salary', categoryName: 'Salary', total: '9000.00' },
  { categoryId: 'cat-rent', categoryName: 'Rent', total: '-3600.00' },
  { categoryId: 'cat-groceries', categoryName: 'Groceries', total: '-1340.10' },
  { categoryId: 'cat-dining', categoryName: 'Dining out', total: '-210.00' },
  { categoryId: 'cat-subscriptions', categoryName: 'Subscriptions', total: '-179.94' },
  { categoryId: null, categoryName: 'Nieskategoryzowane', total: '-45.00' },
];

export const MOCK_CASHFLOW_SUMMARY: CashflowSummary = {
  statementId: 'stmt-2026-w30',
  weekly: {
    periodStart: '2026-07-20',
    periodEnd: '2026-07-26',
    totalIncome: '4500.00',
    totalExpense: '-2555.47',
    categoryBreakdown: WEEKLY_CATEGORY_BREAKDOWN,
    needsReviewCount: 1,
    surplus: '1944.53',
  },
  rollingMonth: {
    periodStart: '2026-07-01',
    periodEnd: '2026-07-26',
    totalIncome: '9000.00',
    totalExpense: '-5375.04',
    categoryBreakdown: ROLLING_MONTH_CATEGORY_BREAKDOWN,
    needsReviewCount: 2,
    surplus: '3624.96',
  },
  fixedCostsStatus: [
    {
      fixedCostId: 'fc-rent',
      fixedCostName: 'Rent',
      expectedAmount: '1800.00',
      actualAmount: '-1800.00',
      status: 'matched',
    },
    {
      fixedCostId: 'fc-internet',
      fixedCostName: 'Internet',
      expectedAmount: '60.00',
      actualAmount: '-75.00',
      status: 'amount_changed',
    },
    {
      fixedCostId: 'fc-insurance',
      fixedCostName: 'Insurance',
      expectedAmount: '120.00',
      actualAmount: null,
      status: 'missing_payment',
    },
  ],
};
