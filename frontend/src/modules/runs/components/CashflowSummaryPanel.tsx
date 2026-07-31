import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { CashflowSummary, PeriodSummary } from '@/modules/common/models/api';
import { CategoryBreakdownChart } from '@/modules/runs/components/CategoryBreakdownChart';
import { FixedCostStatusBadge } from '@/modules/runs/components/FixedCostStatusBadge';
import { StatTile } from '@/modules/runs/components/StatTile';

const AMOUNT_FORMAT = new Intl.NumberFormat('pl-PL', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatAmount(value: string) {
  return AMOUNT_FORMAT.format(Number(value));
}

export interface CashflowSummaryPanelProps {
  summary: CashflowSummary;
}

function PeriodSection({ title, period }: { title: string; period: PeriodSummary }) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-muted-foreground">
        {title} ({period.periodStart} – {period.periodEnd})
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label="Total income" value={formatAmount(period.totalIncome)} />
        <StatTile label="Total expense" value={formatAmount(period.totalExpense)} />
        <StatTile label="Surplus" value={formatAmount(period.surplus)} />
        <StatTile label="Needs review" value={String(period.needsReviewCount)} />
      </div>
      <CategoryBreakdownChart title="Category breakdown" entries={period.categoryBreakdown} />
    </div>
  );
}

export function CashflowSummaryPanel({ summary }: CashflowSummaryPanelProps) {
  return (
    <div className="flex flex-col gap-6">
      {summary.weekly && <PeriodSection title="Weekly" period={summary.weekly} />}
      {summary.rollingMonth && (
        <PeriodSection title="Rolling month to date" period={summary.rollingMonth} />
      )}

      {summary.fixedCostsStatus.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">Fixed costs</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="text-right">Expected</TableHead>
                <TableHead className="text-right">Actual</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summary.fixedCostsStatus.map((entry) => (
                <TableRow key={entry.fixedCostId}>
                  <TableCell>{entry.fixedCostName}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatAmount(entry.expectedAmount)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {entry.actualAmount ? formatAmount(entry.actualAmount) : '—'}
                  </TableCell>
                  <TableCell>
                    <FixedCostStatusBadge status={entry.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
