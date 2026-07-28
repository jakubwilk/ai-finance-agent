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

  it('returns run state', async () => {
    const state = await mockClient.getRunState('any-thread-id');
    expect(state).toHaveProperty('visited');
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

  it('reports healthy status', async () => {
    const health = await mockClient.getHealth();
    expect(health.status).toBe('ok');
    expect(health.database).toBe(true);
    expect(health.ollama).toBe(true);
  });
});
