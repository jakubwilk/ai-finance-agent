import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RunsPage } from './RunsPage';

describe('RunsPage', () => {
  it('shows a loading state, then renders runs from the mock API client', async () => {
    render(<RunsPage />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading/i);

    await waitFor(() => {
      expect(screen.getByText('private-2026-W30')).toBeInTheDocument();
    });

    expect(screen.getByText('company-2026-W30')).toBeInTheDocument();
    expect(screen.getByText('private-2026-W29')).toBeInTheDocument();
    expect(screen.getByText('company-2026-W29')).toBeInTheDocument();
  });

  it('renders every RunStatus as a badge', async () => {
    render(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    expect(screen.getByText('Waiting for review')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('sorts runs by createdAt, newest first', async () => {
    render(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText('company-2026-W29')).toBeInTheDocument();
    });

    const threadCells = screen
      .getAllByRole('row')
      .slice(1)
      .map((row) => row.textContent);
    const order = threadCells.map((text) =>
      ['company-2026-W29', 'private-2026-W30', 'company-2026-W30', 'private-2026-W29'].find((id) =>
        text?.includes(id),
      ),
    );

    expect(order).toEqual([
      'company-2026-W29',
      'private-2026-W30',
      'company-2026-W30',
      'private-2026-W29',
    ]);
  });

  it('links each run to its detail page', async () => {
    render(<RunsPage />);

    await waitFor(() => {
      expect(screen.getByText('private-2026-W30')).toBeInTheDocument();
    });

    const links = screen.getAllByRole('link', { name: 'Details' });
    const hrefs = links.map((link) => link.getAttribute('href'));
    expect(hrefs).toContain('/runs/private-2026-W30');
  });
});
