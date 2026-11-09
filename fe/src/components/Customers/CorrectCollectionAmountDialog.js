import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

/**
 * Admin-only dialog to edit cash collected on a posted debt settlement.
 */
export default function CorrectCollectionAmountDialog({
  open,
  onOpenChange,
  collection,
  onSaved,
}) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && collection) {
      setAmount(String(collection.amount ?? ''));
      setReason('');
    }
  }, [open, collection]);

  if (!collection) return null;

  const submit = async (e) => {
    e.preventDefault();
    const next = Number(amount);
    if (!Number.isFinite(next) || next < 0.01) {
      toast.error('Enter a valid amount (at least 0.01)');
      return;
    }
    setBusy(true);
    try {
      await customersAPI.correctWalletSettlementAmount(collection.id, {
        amount: String(next),
        reason: reason.trim(),
      });
      toast.success('Collection amount updated');
      onOpenChange?.(false);
      onSaved?.();
    } catch (err) {
      const detail =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.response?.data?.amount?.[0] ||
        'Could not update amount';
      toast.error(typeof detail === 'string' ? detail : 'Could not update amount');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit cash collected</DialogTitle>
          <DialogDescription>
            Admin correction for {collection.customer_name || 'customer'} — currently{' '}
            {formatCurrency(collection.amount)}. This updates the wallet and sale
            allocations.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="correct-collection-amount">New amount</Label>
            <Input
              id="correct-collection-amount"
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              disabled={busy}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="correct-collection-reason">Reason (optional)</Label>
            <Input
              id="correct-collection-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Till recount"
              maxLength={200}
              disabled={busy}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange?.(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save amount
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
