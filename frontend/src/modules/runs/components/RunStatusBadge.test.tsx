import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RunStatus } from '@/modules/common/models/api';

import { RunStatusBadge } from './RunStatusBadge';

describe('RunStatusBadge', () => {
  it.each<[RunStatus, string]>([
    ['running', 'Running'],
    ['completed', 'Completed'],
    ['failed', 'Failed'],
    ['waiting_for_review', 'Waiting for review'],
  ])('renders a readable label for status "%s"', (status, expectedLabel) => {
    render(<RunStatusBadge status={status} />);
    expect(screen.getByText(expectedLabel)).toBeInTheDocument();
  });
});
