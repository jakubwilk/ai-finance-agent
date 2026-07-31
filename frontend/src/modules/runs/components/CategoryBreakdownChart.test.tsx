import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { CategoryBreakdownEntry } from '@/modules/common/models/api';

import { CategoryBreakdownChart } from './CategoryBreakdownChart';

const ENTRIES: CategoryBreakdownEntry[] = [
  { categoryId: 'cat-salary', categoryName: 'Salary', total: '4500.00' },
  { categoryId: 'cat-rent', categoryName: 'Rent', total: '-1800.00' },
  { categoryId: null, categoryName: 'Nieskategoryzowane', total: '-45.00' },
];

describe('CategoryBreakdownChart', () => {
  it('renders a legend and a bar per category with its formatted amount', () => {
    render(<CategoryBreakdownChart title="Weekly" entries={ENTRIES} />);

    expect(screen.getByText('Income')).toBeInTheDocument();
    expect(screen.getByText('Expense')).toBeInTheDocument();
    expect(screen.getByText('Salary')).toBeInTheDocument();
    expect(screen.getByText('Rent')).toBeInTheDocument();
    expect(screen.getByText('Nieskategoryzowane')).toBeInTheDocument();
    expect(screen.getByText('4500,00')).toBeInTheDocument();
    expect(screen.getByText('-1800,00')).toBeInTheDocument();
  });

  it('shows a hover tooltip for a bar', () => {
    render(<CategoryBreakdownChart title="Weekly" entries={ENTRIES} />);

    const bar = screen.getByRole('img', { name: /Salary: 4500,00/ });
    fireEvent.mouseEnter(bar);
    expect(screen.getByText('Salary: 4500,00')).toBeInTheDocument();

    fireEvent.mouseLeave(bar);
    expect(screen.queryByText('Salary: 4500,00')).not.toBeInTheDocument();
  });

  it('toggles to a table view with the same data', () => {
    render(<CategoryBreakdownChart title="Weekly" entries={ENTRIES} />);

    fireEvent.click(screen.getByRole('button', { name: 'Show as table' }));

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Category' })).toBeInTheDocument();
    expect(screen.getAllByText('Salary')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'Show chart' }));
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
