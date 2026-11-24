import React, { useEffect, useState } from 'react';

import { formatCurrency } from '../../utils/formatters';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

const REASON_MAX = 300;

/**
 * Ask why an expense or a claim is being returned.
 *
 * Matches the other shop dialogs. The reason is required, 1–300 characters.
 * The person who entered the expense sees that text.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {object|null} props.expense Expense row. Uses number, description, amount, and is_claim.
 * @param {boolean} [props.busy]
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {(reason: string) => void} props.onConfirm Trimmed reason, 1–300 characters.
 */
export default function ReturnExpenseDialog({
  open,
  expense,
  busy = false,
  onOpenChange,
  onConfirm,
}) {
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (open) setReason('');
  }, [open, expense]);

  const text = reason.trim().slice(0, REASON_MAX);
  const claim = Boolean(expense?.is_claim);
  const title = claim ? 'Return this claim' : 'Return this expense';
  const summary = [
    expense?.expense_number,
    expense?.description,
    expense?.amount != null && expense?.amount !== '' ? formatCurrency(expense.amount) : '',
  ].filter(Boolean).join(' · ');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {summary || 'This goes back to the person who entered it.'}
            {' '}
            They will see the reason you write here.
          </DialogDescription>
        </DialogHeader>
        <label className="block space-y-1 text-sm" htmlFor="expense-return-reason">
          <span className="text-muted-foreground">Why are you returning it?</span>
          <Input
            id="expense-return-reason"
            data-testid="expense-return-reason"
            value={reason}
            maxLength={REASON_MAX}
            placeholder="For example, the receipt is missing"
            disabled={busy}
            onChange={(event) => setReason(event.target.value.slice(0, REASON_MAX))}
          />
          <span className="block text-xs text-muted-foreground">{text.length}/{REASON_MAX}</span>
        </label>
        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            data-testid="expense-return-confirm"
            disabled={busy || text.length < 1}
            onClick={() => onConfirm(text)}
          >
            Return
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
