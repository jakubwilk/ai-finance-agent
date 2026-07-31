'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { CategoryBreakdownEntry } from '@/modules/common/models/api';

export interface CategoryBreakdownChartProps {
  title: string;
  entries: CategoryBreakdownEntry[];
}

const AMOUNT_FORMAT = new Intl.NumberFormat('pl-PL', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatAmount(value: string) {
  return AMOUNT_FORMAT.format(Number(value));
}

function entryKey(entry: CategoryBreakdownEntry) {
  return entry.categoryId ?? '__uncategorized__';
}

export function CategoryBreakdownChart({ title, entries }: CategoryBreakdownChartProps) {
  const [showTable, setShowTable] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  const maxAbs = Math.max(1, ...entries.map((entry) => Math.abs(Number(entry.total))));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Button variant="outline" size="sm" onClick={() => setShowTable((prev) => !prev)}>
          {showTable ? 'Show chart' : 'Show as table'}
        </Button>
      </div>

      {!showTable && (
        <>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-blue-500" /> Income
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-500" /> Expense
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {entries.map((entry) => {
              const total = Number(entry.total);
              const isPositive = total >= 0;
              const pct = (Math.abs(total) / maxAbs) * 100;
              const key = entryKey(entry);

              return (
                <div
                  key={key}
                  className="grid grid-cols-[minmax(96px,140px)_1fr_auto] items-center gap-2"
                >
                  <div className="truncate text-sm" title={entry.categoryName}>
                    {entry.categoryName}
                  </div>
                  <div className="relative h-6">
                    <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border" />
                    <div
                      role="img"
                      aria-label={`${entry.categoryName}: ${formatAmount(entry.total)}`}
                      onMouseEnter={() => setHovered(key)}
                      onMouseLeave={() => setHovered((prev) => (prev === key ? null : prev))}
                      className={cn(
                        'absolute inset-y-0 h-6',
                        isPositive
                          ? 'left-1/2 rounded-r-sm bg-blue-500'
                          : 'right-1/2 rounded-l-sm bg-red-500',
                      )}
                      style={{ width: `${pct / 2}%` }}
                    />
                    {hovered === key && (
                      <div
                        className={cn(
                          'absolute -top-7 z-10 rounded border border-border bg-popover px-2 py-1 text-xs whitespace-nowrap text-popover-foreground shadow-md',
                          isPositive ? 'left-1/2' : 'right-1/2',
                        )}
                      >
                        {entry.categoryName}: {formatAmount(entry.total)}
                      </div>
                    )}
                  </div>
                  <div className="text-right text-xs tabular-nums">{formatAmount(entry.total)}</div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {showTable && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => (
              <TableRow key={entryKey(entry)}>
                <TableCell>{entry.categoryName}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatAmount(entry.total)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
