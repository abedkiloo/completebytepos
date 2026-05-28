import React from 'react';
import { AlertTriangle, Wallet, Banknote } from 'lucide-react';

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

/**
 * Confirm dialog shown when the cashier tenders less than the total.
 * Backend records the difference as customer debt.
 */
export function PartialPaymentConfirm({
  open,
  onOpenChange,
  pending,
  customer,
  submitting,
  onConfirm,
}) {
  if (!pending) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-warning" />
            Record balance as debt?
          </DialogTitle>
          <DialogDescription>
            The customer is paying less than the total. The unpaid balance will be added to
            {' '}<strong className="text-foreground">{customer?.name}</strong>'s account.
          </DialogDescription>
        </DialogHeader>

        <dl className="grid grid-cols-2 gap-y-2 rounded-md border bg-muted/40 px-4 py-3 text-sm">
          <dt className="text-muted-foreground">Sale total</dt>
          <dd className="text-right tabular-nums">{formatCurrency(pending.total)}</dd>
          <dt className="text-muted-foreground">Received</dt>
          <dd className="text-right tabular-nums">{formatCurrency(pending.received)}</dd>
          <dt className="font-medium text-foreground">Balance (debt)</dt>
          <dd className="text-right text-base font-semibold tabular-nums text-warning">
            {formatCurrency(pending.balance)}
          </dd>
        </dl>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={submitting}>
            Record sale &amp; debt
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Dialog shown when the cashier tenders more than the total — the cashier picks
 * whether the excess should be returned as change or topped up into the
 * customer's wallet.
 */
export function ExcessPaymentConfirm({
  open,
  onOpenChange,
  pending,
  customer,
  submitting,
  onConfirm,
}) {
  if (!pending) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Where should the excess go?</DialogTitle>
          <DialogDescription>
            The customer has paid {formatCurrency(pending.excess)} more than the sale total.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => onConfirm('change')}
            disabled={submitting}
            className="flex flex-col items-center gap-2 rounded-md border bg-background p-4 text-center hover:border-primary hover:bg-accent disabled:opacity-50"
          >
            <Banknote className="h-7 w-7 text-success" />
            <span className="text-sm font-semibold">Return as change</span>
            <span className="text-xs text-muted-foreground">Cashier hands cash back</span>
          </button>
          <button
            type="button"
            onClick={() => onConfirm('wallet')}
            disabled={submitting}
            className="flex flex-col items-center gap-2 rounded-md border bg-background p-4 text-center hover:border-primary hover:bg-accent disabled:opacity-50"
          >
            <Wallet className="h-7 w-7 text-primary" />
            <span className="text-sm font-semibold">Add to wallet</span>
            <span className="text-xs text-muted-foreground">
              Credit {customer?.name || 'customer'}'s account
            </span>
          </button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
