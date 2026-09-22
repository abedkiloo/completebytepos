import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { formatCurrency } from '../../utils/formatters';
import { buildRollbackPayload, saleIsRollbackable } from '../../utils/saleRefund';
import CommitConfirm from '../Shared/CommitConfirm';
import { saleRollbackRows } from '../../utils/formCommitSummary';

export default function SaleRollbackDialog({ sale, open, onOpenChange, onSubmit, submitting }) {
  const [reason, setReason] = useState('');
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);

  useEffect(() => {
    if (!open) return;
    setReason('');
    setShowCommitConfirm(false);
  }, [open, sale]);

  if (!sale) return null;

  const rollbackable = saleIsRollbackable(sale);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reason.trim() || !rollbackable) return;
    setShowCommitConfirm(true);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Roll back sale</DialogTitle>
            <DialogDescription>
              Requires the sales.rollback permission. The request goes to
              Pending approvals — stock, wallet, and journals reverse only
              after an admin approves. Super Admin can apply immediately.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm">
              <span className="text-muted-foreground">Sale </span>
              <strong>{sale.sale_number}</strong>
              <span className="text-muted-foreground"> · </span>
              {formatCurrency(sale.total)}
            </p>
            <div className="space-y-2">
              <Label htmlFor="sale-rollback-reason">Why is this sale being rolled back? *</Label>
              <textarea
                id="sale-rollback-reason"
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Wrong customer, duplicate checkout, cashier error"
                required
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="destructive" disabled={!rollbackable || !reason.trim()}>
                Continue
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(next) => {
          if (!next && !submitting) setShowCommitConfirm(false);
        }}
        title="Submit sale rollback?"
        description="This is sent to Pending approvals. Stock, money, and accounting reverse only after an admin approves. Super Admin can apply immediately."
        rows={saleRollbackRows(sale, reason)}
        confirmText="Submit for approval"
        submitting={submitting}
        variant="danger"
        onConfirm={() => onSubmit(buildRollbackPayload(reason))}
      />
    </>
  );
}
