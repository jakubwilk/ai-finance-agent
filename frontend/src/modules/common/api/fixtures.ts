import type {
  GraphEdge,
  GraphNode,
  GraphStructureResponse,
  HealthResponse,
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

export const MOCK_RUN_STATE: RunState = {
  verification_ok: true,
  needs_review: true,
  visited: ['ingestion', 'verification_pre', 'extraction', 'verification_post', 'categorization'],
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
