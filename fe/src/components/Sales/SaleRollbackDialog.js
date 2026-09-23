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
import SaleCorrectionCompare from './SaleCorrectionCompare';
import HelpHint from '../Shared/HelpHint';
import { getActionHelp } from '../../utils/actionHelp';

export default function SaleRollbackDialog({ sale, open, onOpenChange, onSubmit, submitting }) {
  const [reason, setReason] = useState('');
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);

  const rollbackHelp = getActionHelp('sale_rollback');

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
            <DialogTitle className="flex items-center gap-2">
              Roll back a mistaken sale
              <HelpHint actionKey="sale_rollback" />
            </DialogTitle>
            <DialogDescription>{rollbackHelp.hover}</DialogDescription>
          </DialogHeader>
          <SaleCorrectionCompare highlight="sale_rollback" />
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
        title={rollbackHelp.confirmTitle}
        description={rollbackHelp.confirmBody}
        helpKey="sale_rollback"
        rows={saleRollbackRows(sale, reason)}
        confirmText="Submit for approval"
        submitting={submitting}
        variant="danger"
        onConfirm={() => onSubmit(buildRollbackPayload(reason))}
      />
    </>
  );
}
