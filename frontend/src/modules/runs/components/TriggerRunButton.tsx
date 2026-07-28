'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { apiClient, type RunSummary } from '@/modules/common/api';

export interface TriggerRunButtonProps {
  onTriggered: (run: RunSummary) => void;
}

export function TriggerRunButton({ onTriggered }: TriggerRunButtonProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = () => {
    setPending(true);
    setError(null);

    apiClient
      .triggerRun()
      .then((run) => {
        onTriggered(run);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to trigger run');
      })
      .finally(() => {
        setPending(false);
      });
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <Button onClick={handleClick} disabled={pending}>
        {pending ? 'Starting…' : 'Run now'}
      </Button>
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
