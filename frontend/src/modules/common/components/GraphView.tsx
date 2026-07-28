'use client';

import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react';
import { useMemo } from 'react';

import type { GraphEdge, GraphNode } from '@/modules/common/models/api';
import { getLayoutedElements } from '@/modules/common/utils/layout';

const KIND_CLASSES: Record<NonNullable<GraphNode['kind']>, string> = {
  default: '',
  alert: '!border-destructive !bg-destructive/10',
  interrupt: '!border-amber-500 !bg-amber-500/10',
};

const ACTIVE_CLASS = '!border-primary !ring-2 !ring-primary';

export interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** Highlights the nodes currently executing/next-up for the run being viewed, if any. */
  activeNodeIds?: string[];
}

export function GraphView({ nodes, edges, activeNodeIds }: GraphViewProps) {
  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
    const rawNodes: Node[] = nodes.map((node) => ({
      id: node.id,
      position: { x: 0, y: 0 },
      data: { label: node.label },
      className: [
        KIND_CLASSES[node.kind ?? 'default'],
        activeNodeIds?.includes(node.id) ? ACTIVE_CLASS : '',
      ]
        .filter(Boolean)
        .join(' '),
    }));

    const rawEdges: Edge[] = edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
    }));

    return getLayoutedElements(rawNodes, rawEdges, 'TB');
  }, [nodes, edges, activeNodeIds]);

  return (
    <div className="h-full w-full">
      <ReactFlow nodes={flowNodes} edges={flowEdges} fitView nodesDraggable={false}>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
