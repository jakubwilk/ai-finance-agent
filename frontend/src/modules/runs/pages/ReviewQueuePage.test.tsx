import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import { resetMockRuns } from '@/modules/common/api/mockClient';

import { ReviewQueuePage } from './ReviewQueuePage';

describe('ReviewQueuePage', () => {
  beforeEach(() => {
    resetMockRuns();
  });

  it('shows a loading state, then renders pending reviews', async () => {
    render(<ReviewQueuePage threadId="company-2026-W30" />);

    expect(screen.getByRole('status')).toHaveTextContent(/loading/i);

    await waitFor(() => {
      expect(screen.getByText('Płatność kartą - sklep spożywczy')).toBeInTheDocument();
    });

    expect(screen.getByText('Przelew przychodzący')).toBeInTheDocument();
  });

  it('disables submit until at least one category is chosen', async () => {
    const user = userEvent.setup();
    render(<ReviewQueuePage threadId="company-2026-W30" />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /submit decisions/i })).toBeDisabled();
    });

    const trigger = screen.getByRole('combobox', {
      name: 'Category for Płatność kartą - sklep spożywczy',
    });
    await user.click(trigger);
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('Groceries'));

    expect(screen.getByRole('button', { name: /submit decisions \(1\)/i })).toBeEnabled();
  });

  it('submits decisions and removes resolved reviews from the queue', async () => {
    const user = userEvent.setup();
    render(<ReviewQueuePage threadId="company-2026-W30" />);

    await waitFor(() => {
      expect(screen.getByText('Płatność kartą - sklep spożywczy')).toBeInTheDocument();
    });

    const trigger = screen.getByRole('combobox', {
      name: 'Category for Płatność kartą - sklep spożywczy',
    });
    await user.click(trigger);
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('Groceries'));

    await user.click(screen.getByRole('button', { name: /submit decisions/i }));

    await waitFor(() => {
      expect(screen.queryByText('Płatność kartą - sklep spożywczy')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Przelew przychodzący')).toBeInTheDocument();
  });

  it('shows an empty state once every review is resolved', async () => {
    const user = userEvent.setup();
    render(<ReviewQueuePage threadId="company-2026-W30" />);

    await waitFor(() => {
      expect(screen.getByText('Płatność kartą - sklep spożywczy')).toBeInTheDocument();
    });

    const descriptions = [
      'Płatność kartą - sklep spożywczy',
      'Przelew przychodzący',
      'Płatność cykliczna - streaming',
    ];
    for (const description of descriptions) {
      const trigger = screen.getByRole('combobox', { name: `Category for ${description}` });
      await user.click(trigger);
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('Groceries'));
    }

    await user.click(screen.getByRole('button', { name: /submit decisions/i }));

    await waitFor(() => {
      expect(screen.getByText('All reviews resolved.')).toBeInTheDocument();
    });
  });

  it('links back to the run detail and runs list', async () => {
    render(<ReviewQueuePage threadId="company-2026-W30" />);

    expect(screen.getByRole('link', { name: '← Back to run' })).toHaveAttribute(
      'href',
      '/runs/company-2026-W30',
    );
    expect(screen.getByRole('link', { name: '← Back to runs' })).toHaveAttribute('href', '/runs');
  });
});
