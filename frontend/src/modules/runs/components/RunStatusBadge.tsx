import { Badge } from '@/components/ui/badge';
import type { RunStatus } from '@/modules/common/models/api';

const STATUS_LABEL: Record<RunStatus, string> = {
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  waiting_for_review: 'Waiting for review',
};

const STATUS_CLASSES: Record<RunStatus, string> = {
  running: '!bg-blue-500/10 !text-blue-600 dark:!text-blue-400',
  completed: '!bg-emerald-500/10 !text-emerald-600 dark:!text-emerald-400',
  waiting_for_review: '!bg-amber-500/10 !text-amber-600 dark:!text-amber-400',
  failed: '',
};

export interface RunStatusBadgeProps {
  status: RunStatus;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  return (
    <Badge
      variant={status === 'failed' ? 'destructive' : 'outline'}
      className={STATUS_CLASSES[status]}
    >
      {STATUS_LABEL[status]}
    </Badge>
  );
}
