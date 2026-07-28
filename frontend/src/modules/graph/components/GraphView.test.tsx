import { render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';

import type { GraphEdge, GraphNode } from '@/modules/common/models/api';
import { mockReactFlow } from '@/test/mockReactFlow';

import { GraphView } from './GraphView';

beforeAll(() => {
  mockReactFlow();
});

const nodes: GraphNode[] = [
  { id: 'a', label: 'Node A' },
  { id: 'b', label: 'Node B', kind: 'alert' },
  { id: 'c', label: 'Node C', kind: 'interrupt' },
];

const edges: GraphEdge[] = [
  { id: 'a-b', source: 'a', target: 'b', label: 'fail' },
  { id: 'a-c', source: 'a', target: 'c' },
];

describe('GraphView', () => {
  it('renders a node per GraphNode entry', async () => {
    render(<GraphView nodes={nodes} edges={edges} />);

    await waitFor(() => {
      expect(screen.getByText('Node A')).toBeInTheDocument();
      expect(screen.getByText('Node B')).toBeInTheDocument();
      expect(screen.getByText('Node C')).toBeInTheDocument();
    });
  });

  it('highlights the active node', async () => {
    render(<GraphView nodes={nodes} edges={edges} activeNodeId="a" />);

    await waitFor(() => {
      const activeNode = screen.getByText('Node A').closest('.react-flow__node');
      expect(activeNode?.className).toContain('ring-primary');
    });
  });

  it('marks alert and interrupt nodes with a distinct style', async () => {
    render(<GraphView nodes={nodes} edges={edges} />);

    await waitFor(() => {
      const alertNode = screen.getByText('Node B').closest('.react-flow__node');
      const interruptNode = screen.getByText('Node C').closest('.react-flow__node');
      expect(alertNode?.className).toContain('border-destructive');
      expect(interruptNode?.className).toContain('border-amber-500');
    });
  });
});
