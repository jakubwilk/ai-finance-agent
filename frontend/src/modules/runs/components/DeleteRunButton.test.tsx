import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '@/modules/common/api';

import { DeleteRunButton } from './DeleteRunButton';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DeleteRunButton', () => {
  it('does not call deleteRun when the confirmation dialog is cancelled', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteRun');
    const onDeleted = vi.fn();
    render(<DeleteRunButton threadId="abc" onDeleted={onDeleted} />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('alertdialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });
    expect(deleteSpy).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it('calls deleteRun and onDeleted with the threadId on confirm', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'deleteRun').mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    render(<DeleteRunButton threadId="abc" onDeleted={onDeleted} />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(onDeleted).toHaveBeenCalledWith('abc');
    });
    expect(deleteSpy).toHaveBeenCalledWith('abc');
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('shows an error message and keeps the dialog open on failure', async () => {
    vi.spyOn(apiClient, 'deleteRun').mockRejectedValueOnce(new Error('backend unreachable'));
    const onDeleted = vi.fn();
    render(<DeleteRunButton threadId="abc" onDeleted={onDeleted} />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('alertdialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(within(dialog).getByRole('alert')).toHaveTextContent('backend unreachable');
    });
    expect(onDeleted).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });
});
