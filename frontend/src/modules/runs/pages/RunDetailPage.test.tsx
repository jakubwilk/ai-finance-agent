import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';

import { mockReactFlow } from '@/test/mockReactFlow';

import { RunDetailPage } from './RunDetailPage';

beforeAll(() => {
  mockReactFlow();
});

describe('RunDetailPage', () => {
  it('shows a loading state, then the checkpoint timeline', async () => {
    render(<RunDetailPage threadId="private-2026-W30" />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading/i);

    await waitFor(() => {
      expect(screen.getByText('Step 0')).toBeInTheDocument();
    });

    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
  });

  it('selects the most recent checkpoint by default and highlights its next node', async () => {
    render(<RunDetailPage threadId="private-2026-W30" />);

    await waitFor(() => {
      expect(screen.getByText('Next: extraction')).toBeInTheDocument();
    });

    await waitFor(() => {
      const nextNode = screen.getByText('extraction subgraph').closest('.react-flow__node');
      expect(nextNode?.className).toContain('ring-primary');
    });
  });

  it('updates the state panel when an earlier checkpoint is selected', async () => {
    render(<RunDetailPage threadId="private-2026-W30" />);

    await waitFor(() => {
      expect(screen.getByText('Step 0')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Step 0'));

    await waitFor(() => {
      expect(screen.getByText('Next: ingestion')).toBeInTheDocument();
    });
  });

  it('links back to the runs list', async () => {
    render(<RunDetailPage threadId="private-2026-W30" />);

    const backLink = screen.getByRole('link', { name: /back to runs/i });
    expect(backLink).toHaveAttribute('href', '/runs');
  });
});
