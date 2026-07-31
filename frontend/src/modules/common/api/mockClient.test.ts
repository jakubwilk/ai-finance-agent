import { beforeEach, describe, expect, it } from 'vitest';

import { mockClient, resetMockRuns } from '@/modules/common/api/mockClient';
import type { RunStatus } from '@/modules/common/models/api';

describe('mockClient', () => {
  beforeEach(() => {
    resetMockRuns();
  });

  it('returns the master graph mermaid diagram', async () => {
    const result = await mockClient.getGraphStructure();
    expect(result.mermaid).toContain('flowchart TD');
    expect(result.mermaid).toContain('START([start])');
    expect(result.mermaid).toContain('MAIL --> END');
  });

  it('returns runs covering every RunStatus', async () => {
    const runs = await mockClient.listRuns();
    const statuses = new Set(runs.map((run) => run.status));
    const expected: RunStatus[] = ['running', 'completed', 'failed', 'waiting_for_review'];

    expect(runs.length).toBeGreaterThan(0);
    for (const status of expected) {
      expect(statuses.has(status)).toBe(true);
    }
  });

  it('creates a new running run on trigger', async () => {
    const run = await mockClient.triggerRun();
    expect(run.status).toBe('running');
    expect(run.threadId).toBeTruthy();
  });

  it('makes triggered runs show up in a subsequent listRuns call', async () => {
    const before = await mockClient.listRuns();
    const triggered = await mockClient.triggerRun();
    const after = await mockClient.listRuns();

    expect(after.length).toBe(before.length + 1);
    expect(after.map((run) => run.threadId)).toContain(triggered.threadId);
  });

  it('returns a cashflow summary with weekly and rolling month periods', async () => {
    const summary = await mockClient.getCashflowSummary('any-thread-id');
    expect(summary.weekly?.categoryBreakdown.length).toBeGreaterThan(0);
    expect(summary.rollingMonth?.categoryBreakdown.length).toBeGreaterThan(0);
    expect(summary.fixedCostsStatus.length).toBeGreaterThan(0);
  });

  it('returns categories', async () => {
    const categories = await mockClient.getCategories();
    expect(categories.length).toBeGreaterThan(0);
    expect(categories[0]).toHaveProperty('name');
  });

  it('returns run state with values and pending reviews', async () => {
    const state = await mockClient.getRunState('any-thread-id');
    expect(state.values).toHaveProperty('visited');
    expect(state.pendingReviews.length).toBeGreaterThan(0);
  });

  it('returns run history as an ordered list of checkpoints', async () => {
    const history = await mockClient.getRunHistory('any-thread-id');
    expect(history.length).toBeGreaterThan(0);
    expect(history[0]).toHaveProperty('checkpointId');
    expect(history[0]).toHaveProperty('next');
  });

  it('returns state from resumeRun', async () => {
    const state = await mockClient.resumeRun('any-thread-id', { category: 'groceries' });
    expect(state).toBeTruthy();
  });

  it('resumeRun resolves decided pending reviews and leaves the rest', async () => {
    const before = await mockClient.getRunState('company-2026-W30');
    const [first, ...rest] = before.pendingReviews;

    const after = await mockClient.resumeRun('company-2026-W30', {
      decisions: { [first.transactionId]: 'Groceries' },
    });

    expect(after.pendingReviews.map((r) => r.transactionId)).not.toContain(first.transactionId);
    expect(after.pendingReviews).toHaveLength(rest.length);
  });

  it('resumeRun flips the run to completed once every pending review is decided', async () => {
    const before = await mockClient.getRunState('company-2026-W30');
    const decisions = Object.fromEntries(
      before.pendingReviews.map((review) => [review.transactionId, 'Groceries']),
    );

    await mockClient.resumeRun('company-2026-W30', { decisions });

    const runs = await mockClient.listRuns();
    const run = runs.find((r) => r.threadId === 'company-2026-W30');
    expect(run?.status).toBe('completed');
  });

  it('deleteRun removes the run from a subsequent listRuns call', async () => {
    const before = await mockClient.listRuns();
    const [target] = before;

    await mockClient.deleteRun(target.threadId);
    const after = await mockClient.listRuns();

    expect(after.length).toBe(before.length - 1);
    expect(after.map((run) => run.threadId)).not.toContain(target.threadId);
  });

  it('reports healthy status', async () => {
    const health = await mockClient.getHealth();
    expect(health.status).toBe('ok');
    expect(health.database).toBe(true);
    expect(health.ollama).toBe(true);
  });
});
