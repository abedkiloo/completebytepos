import React from 'react';
import { CheckCircle2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { formatCurrency } from '../../../utils/formatters';
import { paymentMethodLabel } from '../../../utils/paymentMethods';
import {
  saleCommitConfirmLabel,
  saleCommitTitle,
} from '../../../utils/saleCommitSummary';

/**
 * Pre-commit confirmation with payment summary. Use before salesAPI.create /
 * checkout so cashiers review totals for full, partial, or pay-later sales.
 */
export function SaleCommitConfirm({
  open,
  onOpenChange,
  summary,
  submitting = false,
  onConfirm,
}) {
  if (!summary) return null;
  const kind = summary.kind || 'full';
  const title = saleCommitTitle(kind);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            {title}
          </DialogTitle>
          <DialogDescription>
            Review the payment summary, then confirm to save this sale. This cannot be
            undone from the register.
          </DialogDescription>
        </DialogHeader>

        <dl className="grid grid-cols-2 gap-y-2 rounded-md border bg-muted/40 px-4 py-3 text-sm">
          {summary.itemCount > 0 ? (
            <>
              <dt className="text-muted-foreground">Items</dt>
              <dd className="text-right tabular-nums">{summary.itemCount}</dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Payment method</dt>
          <dd className="text-right">{paymentMethodLabel(summary.paymentMethod)}</dd>
          {summary.paymentReference ? (
            <>
              <dt className="text-muted-foreground">Reference</dt>
              <dd className="text-right font-mono text-xs">{summary.paymentReference}</dd>
            </>
          ) : null}
          {summary.customerName ? (
            <>
              <dt className="text-muted-foreground">Customer</dt>
              <dd className="text-right">{summary.customerName}</dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Sale total</dt>
          <dd className="text-right tabular-nums">{formatCurrency(summary.total)}</dd>
          <dt className="text-muted-foreground">
            {kind === 'pay_later' ? 'Collected now' : 'Amount paid'}
          </dt>
          <dd className="text-right tabular-nums">{formatCurrency(summary.received)}</dd>
          {kind === 'full' && summary.change > 0 ? (
            <>
              <dt className="font-medium text-foreground">Change</dt>
              <dd className="text-right text-base font-semibold tabular-nums text-success">
                {formatCurrency(summary.change)}
              </dd>
            </>
          ) : null}
          {kind !== 'full' ? (
            <>
              <dt className="font-medium text-foreground">
                {kind === 'pay_later' ? 'Amount due (pay later)' : 'Balance (debt)'}
              </dt>
              <dd className="text-right text-base font-semibold tabular-nums text-warning">
                {formatCurrency(summary.balance)}
              </dd>
            </>
          ) : null}
        </dl>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={submitting}>
            {submitting ? 'Saving…' : saleCommitConfirmLabel(kind)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

