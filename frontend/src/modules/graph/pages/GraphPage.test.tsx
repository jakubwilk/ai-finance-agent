import { render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';

import { mockReactFlow } from '@/test/mockReactFlow';

import { GraphPage } from './GraphPage';

beforeAll(() => {
  mockReactFlow();
});

describe('GraphPage', () => {
  it('shows a loading state, then renders the graph from the mock API client', async () => {
    render(<GraphPage />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading/i);

    await waitFor(
      () => {
        expect(screen.getByText('ingestion subgraph')).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
  });
});
