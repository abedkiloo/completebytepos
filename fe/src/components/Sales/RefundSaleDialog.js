import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { formatCurrency } from '../../utils/formatters';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { isMakerCheckerEnabled, makerCheckerReasonCopy } from '../../utils/makerChecker';
import {
  buildFullRefundPayload,
  buildPartialRefundPayload,
  saleIsRefundable,
} from '../../utils/saleRefund';
import {
  saleItemRefundableQuantity,
  saleItemVariantLabel,
} from '../../utils/saleItemDisplay';
import {
  buildDuplicateRefundQtyMap,
  detectDuplicateSaleLineGroups,
  duplicateExcessSaleItemIds,
  hasDuplicateSaleLines,
} from '../../utils/detectDuplicateSaleLines';

export default function RefundSaleDialog({ sale, open, onOpenChange, onSubmit, submitting }) {
  const [reason, setReason] = useState('');
  const [mode, setMode] = useState('full');
  const [lineQty, setLineQty] = useState({});
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const refundCopy = makerCheckerReasonCopy('sale_refund');

  const duplicateGroups = useMemo(
    () => detectDuplicateSaleLineGroups(sale?.items || []),
    [sale]
  );
  const duplicateExcessIds = useMemo(
    () => new Set(duplicateExcessSaleItemIds(sale?.items || [])),
    [sale]
  );
  const showDuplicateHelper = hasDuplicateSaleLines(sale?.items);

  useEffect(() => {
    if (!open || !sale) return;
    setReason('');
    setMode('full');
    const initial = {};
    (sale.items || []).forEach((item) => {
      initial[item.id] = saleItemRefundableQuantity(item);
    });
    setLineQty(initial);
  }, [open, sale]);

  if (!sale) return null;

  const refundable = saleIsRefundable(sale);

  const applyDuplicateRefundPreset = () => {
    setMode('partial');
    setLineQty(buildDuplicateRefundQtyMap(sale.items || []));
  };

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
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
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
              {makerCheckerOn
                ? refundCopy.summary
                : 'Stock is returned to inventory, revenue and cash books are reversed, and any customer account or wallet balance from this sale is adjusted. The original sale is kept for audit — it is not deleted.'}
            </p>

            {showDuplicateHelper ? (
              <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50/80 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="border-amber-400 text-amber-900">
                    Duplicate lines detected
                  </Badge>
                  <span className="text-xs text-amber-950">
                    {duplicateGroups.length} product
                    {duplicateGroups.length === 1 ? '' : 's'} appear on multiple lines.
                  </span>
                </div>
                <p className="text-xs text-amber-950">
                  Use &ldquo;Refund duplicate lines&rdquo; to void only the extra rows (keeps the
                  first line per product/variant). Stock, wallet, and reports are adjusted for the
                  refunded quantities only.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={applyDuplicateRefundPreset}
                >
                  Refund duplicate lines
                </Button>
              </div>
            ) : null}

            <div className="flex flex-col gap-2 text-sm sm:flex-row sm:gap-4">
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
                {(sale.items || []).map((item) => {
                  const variantLabel = saleItemVariantLabel(item);
                  const refundableQty = saleItemRefundableQuantity(item);
                  const refunded = parseInt(item.quantity_refunded, 10) || 0;
                  const isDuplicateExcess = duplicateExcessIds.has(item.id);
                  return (
                    <div
                      key={item.id}
                      className="flex items-start justify-between gap-2 border-b border-dashed border-border/60 py-2 text-sm last:border-0"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">
                          {item.product_name || item.product?.name}
                          {isDuplicateExcess ? (
                            <Badge variant="outline" className="ml-2 text-[10px]">
                              Duplicate
                            </Badge>
                          ) : null}
                        </div>
                        {variantLabel ? (
                          <div className="text-xs text-muted-foreground">{variantLabel}</div>
                        ) : null}
                        <div className="text-xs text-muted-foreground">
                          Sold {item.quantity}
                          {refunded > 0 ? ` · ${refunded} already refunded` : ''}
                          {refundableQty < item.quantity
                            ? ` · ${refundableQty} refundable`
                            : ''}
                        </div>
                      </div>
                      <input
                        type="number"
                        min={0}
                        max={refundableQty}
                        className="w-16 shrink-0 rounded border px-2 py-1"
                        value={lineQty[item.id] ?? 0}
                        disabled={refundableQty <= 0}
                        onChange={(e) =>
                          setLineQty((prev) => ({
                            ...prev,
                            [item.id]: e.target.value,
                          }))
                        }
                      />
                    </div>
                  );
                })}
              </div>
            )}
            <ChangeReasonField
              value={reason}
              onChange={setReason}
              requiresApproval={makerCheckerOn}
              context={makerCheckerOn ? 'sale_refund' : 'default'}
              label={makerCheckerOn ? refundCopy.label : 'Reason for void / refund'}
              placeholder={
                makerCheckerOn
                  ? refundCopy.placeholder
                  : 'Why is this sale being voided or refunded?'
              }
              hint={
                makerCheckerOn
                  ? undefined
                  : 'Required for audit — the original sale is kept on record.'
              }
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="destructive" disabled={submitting || !reason.trim()}>
                {submitting
                  ? 'Processing…'
                  : makerCheckerOn
                    ? 'Submit for approval'
                    : 'Confirm void / refund'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
