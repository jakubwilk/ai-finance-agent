import dagre from '@dagrejs/dagre';
import { Position, type Edge, type Node } from '@xyflow/react';

const NODE_WIDTH = 172;
const NODE_HEIGHT = 40;

export type LayoutDirection = 'TB' | 'LR';

/**
 * Computes node positions with dagre. @xyflow/react's get_graph() output
 * has no x/y coordinates of its own (see docs/14-spec-frontend-ui.md),
 * so layout has to be derived separately — pattern per
 * reactflow.dev/examples/layout/dagre.
 */
export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: LayoutDirection = 'TB',
): { nodes: Node[]; edges: Edge[] } {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  const isHorizontal = direction === 'LR';
  graph.setGraph({ rankdir: direction });

  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target);
  }

  dagre.layout(graph);

  const layoutedNodes = nodes.map((node) => {
    const { x, y } = graph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: {
        x: x - NODE_WIDTH / 2,
        y: y - NODE_HEIGHT / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
