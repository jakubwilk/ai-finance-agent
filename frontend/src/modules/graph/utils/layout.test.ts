import type { Edge, Node } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

import { getLayoutedElements } from './layout';

const nodes: Node[] = [
  { id: 'a', position: { x: 0, y: 0 }, data: { label: 'a' } },
  { id: 'b', position: { x: 0, y: 0 }, data: { label: 'b' } },
  { id: 'c', position: { x: 0, y: 0 }, data: { label: 'c' } },
];

const edges: Edge[] = [
  { id: 'a-b', source: 'a', target: 'b' },
  { id: 'b-c', source: 'b', target: 'c' },
];

describe('getLayoutedElements', () => {
  it('assigns a computed position to every node', () => {
    const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges, 'TB');

    expect(layoutedNodes).toHaveLength(nodes.length);
    for (const node of layoutedNodes) {
      expect(Number.isFinite(node.position.x)).toBe(true);
      expect(Number.isFinite(node.position.y)).toBe(true);
    }
  });

  it('lays out top-to-bottom nodes with increasing y', () => {
    const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges, 'TB');
    const byId = Object.fromEntries(layoutedNodes.map((n) => [n.id, n]));

    expect(byId.a.position.y).toBeLessThan(byId.b.position.y);
    expect(byId.b.position.y).toBeLessThan(byId.c.position.y);
    expect(byId.a.sourcePosition).toBe('bottom');
    expect(byId.a.targetPosition).toBe('top');
  });

  it('lays out left-to-right nodes with increasing x', () => {
    const { nodes: layoutedNodes } = getLayoutedElements(nodes, edges, 'LR');
    const byId = Object.fromEntries(layoutedNodes.map((n) => [n.id, n]));

    expect(byId.a.position.x).toBeLessThan(byId.b.position.x);
    expect(byId.b.position.x).toBeLessThan(byId.c.position.x);
    expect(byId.a.sourcePosition).toBe('right');
    expect(byId.a.targetPosition).toBe('left');
  });

  it('preserves edges unchanged', () => {
    const { edges: layoutedEdges } = getLayoutedElements(nodes, edges, 'TB');
    expect(layoutedEdges).toEqual(edges);
  });
});
