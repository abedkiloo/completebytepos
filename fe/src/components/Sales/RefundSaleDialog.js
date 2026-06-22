import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { formatCurrency } from '../../utils/formatters';
import {
  buildFullRefundPayload,
  buildPartialRefundPayload,
  saleIsRefundable,
} from '../../utils/saleRefund';

export default function RefundSaleDialog({ sale, open, onOpenChange, onSubmit, submitting }) {
  const [reason, setReason] = useState('');
  const [mode, setMode] = useState('full');
  const [lineQty, setLineQty] = useState({});

  useEffect(() => {
    if (!open || !sale) return;
    setReason('');
    setMode('full');
    const initial = {};
    (sale.items || []).forEach((item) => {
      initial[item.id] = item.quantity;
    });
    setLineQty(initial);
  }, [open, sale]);

  if (!sale) return null;

  const refundable = saleIsRefundable(sale);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reason.trim()) return;
    if (mode === 'full') {
      onSubmit(buildFullRefundPayload(reason));
      return;
    }
    const items = (sale.items || [])
      .map((item) => ({
        sale_item_id: item.id,
        quantity: parseInt(lineQty[item.id], 10) || 0,
      }))
      .filter((row) => row.quantity > 0);
    onSubmit(buildPartialRefundPayload(reason, items));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Void or refund sale {sale.sale_number}</DialogTitle>
        </DialogHeader>
        {!refundable ? (
          <p className="text-sm text-muted-foreground">
            This sale cannot be voided (already fully refunded or not completed).
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Original sale total {formatCurrency(sale.total)} · refundable{' '}
              {formatCurrency(sale.refundable_remaining ?? sale.total)}
            </p>
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">
              Stock is returned to inventory, revenue and cash books are reversed, and any
              customer account or wallet balance from this sale is adjusted. The original sale
              is kept for audit — it is not deleted.
            </p>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="refund_mode"
                  checked={mode === 'full'}
                  onChange={() => setMode('full')}
                />
                Full void (refund entire sale)
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="refund_mode"
                  checked={mode === 'partial'}
                  onChange={() => setMode('partial')}
                  disabled={!(sale.items || []).length}
                />
                Partial (by line)
              </label>
            </div>
            {mode === 'partial' && (
              <div className="space-y-2 rounded-md border p-3">
                <Label>Quantities to return</Label>
                {(sale.items || []).map((item) => (
                  <div key={item.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate">
                      {item.product_name || item.product?.name} × sold {item.quantity}
                    </span>
                    <input
                      type="number"
                      min={0}
                      max={item.quantity}
                      className="w-16 rounded border px-2 py-1"
                      value={lineQty[item.id] ?? 0}
                      onChange={(e) =>
                        setLineQty((prev) => ({
                          ...prev,
                          [item.id]: e.target.value,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            )}
            <ChangeReasonField
              value={reason}
              onChange={setReason}
              label="Reason for void / refund"
              placeholder="Why is this sale being voided or refunded?"
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="destructive" disabled={submitting || !reason.trim()}>
                {submitting ? 'Processing…' : 'Confirm void / refund'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
