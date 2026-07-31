import { Badge } from '@/components/ui/badge';
import type { FixedCostStatusEntry } from '@/modules/common/models/api';

type FixedCostStatus = FixedCostStatusEntry['status'];

const STATUS_LABEL: Record<FixedCostStatus, string> = {
  matched: 'Matched',
  amount_changed: 'Amount changed',
  missing_payment: 'Missing payment',
};

const STATUS_CLASSES: Record<FixedCostStatus, string> = {
  matched: '!bg-emerald-500/10 !text-emerald-600 dark:!text-emerald-400',
  amount_changed: '!bg-amber-500/10 !text-amber-600 dark:!text-amber-400',
  missing_payment: '',
};

export interface FixedCostStatusBadgeProps {
  status: FixedCostStatus;
}

export function FixedCostStatusBadge({ status }: FixedCostStatusBadgeProps) {
  return (
    <Badge
      variant={status === 'missing_payment' ? 'destructive' : 'outline'}
      className={STATUS_CLASSES[status]}
    >
      {STATUS_LABEL[status]}
    </Badge>
  );
}
