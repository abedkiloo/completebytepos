import React from 'react';
import { cn } from '../../lib/cn';
import { Button } from '../ui/button';
import { PageLoading } from '../page';
import { Badge } from '../ui/badge';

export function ReportPanel({ children }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm sm:p-6">{children}</div>
  );
}

export function ReportLoading() {
  return <PageLoading rows={6} />;
}

export function ReportEmpty({ children }) {
  return (
    <div className="rounded-lg border border-dashed bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export function ReportDownloadButton({ onClick, label = 'Download PDF' }) {
  return (
    <Button type="button" variant="outline" size="sm" onClick={onClick}>
      {label}
    </Button>
  );
}

export function amt(positive, negative, debit, credit) {
  return cn(
    'text-right tabular-nums font-medium',
    (positive || debit) && 'text-emerald-700 dark:text-emerald-400',
    (negative || credit) && 'text-destructive'
  );
}

export function AccountStatusBadge({ active }) {
  return (
    <Badge
      variant="secondary"
      className={
        active
          ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-100'
          : 'bg-red-100 text-red-800 hover:bg-red-100'
      }
    >
      {active ? 'Active' : 'Inactive'}
    </Badge>
  );
}

export const R = {
  header: 'mb-6 flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-start sm:justify-between',
  headerText: 'space-y-1',
  title: 'text-lg font-semibold',
  meta: 'text-sm text-muted-foreground',
  grid3: 'mb-6 grid gap-4 lg:grid-cols-3',
  grid2: 'mb-6 grid gap-4 lg:grid-cols-2',
  section: 'rounded-lg border p-4',
  sectionTitle: 'mb-3 border-b pb-2 text-base font-semibold',
  table: 'w-full text-sm',
  accountTd: 'border-b border-border/40 py-2',
  totalRow: 'border-t-2',
  summaryWrap: 'mt-6 border-t pt-4',
  summaryItem: 'flex items-center justify-between rounded-md bg-muted/40 px-4 py-3 font-semibold',
  summaryHighlight:
    'flex items-center justify-between rounded-md border-2 border-primary/30 bg-primary/5 px-4 py-3 font-semibold',
  cashItem: 'flex items-center justify-between border-b border-border/50 py-2 text-sm',
  cashTotal: 'flex items-center justify-between border-t-2 pt-3 text-base font-semibold',
  ledgerInfo: 'mb-4 grid gap-3 rounded-lg bg-muted/30 p-4 sm:grid-cols-2',
  infoItem: 'flex items-center justify-between gap-2 text-sm',
  tableWrap: 'overflow-x-auto rounded-lg border',
  thead: 'border-b bg-muted/40 text-left text-xs font-medium text-muted-foreground',
  th: 'px-3 py-2',
  td: 'px-3 py-2',
  tr: 'border-b hover:bg-muted/30',
  tfoot: 'border-t bg-muted/40 font-semibold',
  capitalize: 'capitalize',
  amount: 'text-right tabular-nums font-medium',
};
