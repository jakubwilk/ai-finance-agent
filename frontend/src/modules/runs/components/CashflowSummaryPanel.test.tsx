import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MOCK_CASHFLOW_SUMMARY } from '@/modules/common/api/fixtures';

import { CashflowSummaryPanel } from './CashflowSummaryPanel';

describe('CashflowSummaryPanel', () => {
  it('renders a section for both the weekly and rolling month periods', () => {
    render(<CashflowSummaryPanel summary={MOCK_CASHFLOW_SUMMARY} />);

    expect(screen.getByText(/^Weekly/)).toBeInTheDocument();
    expect(screen.getByText(/^Rolling month to date/)).toBeInTheDocument();
  });

  it('renders stat tiles for income, expense, surplus and needs review', () => {
    render(<CashflowSummaryPanel summary={MOCK_CASHFLOW_SUMMARY} />);

    expect(screen.getAllByText('Total income')).toHaveLength(2);
    expect(screen.getAllByText('Total expense')).toHaveLength(2);
    expect(screen.getAllByText('Surplus')).toHaveLength(2);
    expect(screen.getAllByText('Needs review')).toHaveLength(2);
  });

  it('renders a fixed costs table with a status badge per row', () => {
    render(<CashflowSummaryPanel summary={MOCK_CASHFLOW_SUMMARY} />);

    const fixedCostsTable = screen.getByRole('table');
    expect(within(fixedCostsTable).getByText('Rent')).toBeInTheDocument();
    expect(within(fixedCostsTable).getByText('Matched')).toBeInTheDocument();
    expect(within(fixedCostsTable).getByText('Amount changed')).toBeInTheDocument();
    expect(within(fixedCostsTable).getByText('Missing payment')).toBeInTheDocument();
  });
});
