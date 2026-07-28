import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '@/modules/common/api';

import { TriggerRunButton } from './TriggerRunButton';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('TriggerRunButton', () => {
  it('calls onTriggered with the new run on success', async () => {
    const onTriggered = vi.fn();
    render(<TriggerRunButton onTriggered={onTriggered} />);

    fireEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(screen.getByRole('button')).toHaveTextContent('Starting…');
    expect(screen.getByRole('button')).toBeDisabled();

    await waitFor(() => {
      expect(onTriggered).toHaveBeenCalledTimes(1);
    });

    const [run] = onTriggered.mock.calls[0];
    expect(run.status).toBe('running');
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('shows an error message and re-enables the button on failure', async () => {
    vi.spyOn(apiClient, 'triggerRun').mockRejectedValueOnce(new Error('backend unreachable'));
    const onTriggered = vi.fn();
    render(<TriggerRunButton onTriggered={onTriggered} />);

    fireEvent.click(screen.getByRole('button', { name: 'Run now' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('backend unreachable');
    });

    expect(onTriggered).not.toHaveBeenCalled();
    expect(screen.getByRole('button')).not.toBeDisabled();
  });
});
