import React, { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import SaleChannelIcon, { saleChannelLabel } from './SaleChannelIcon';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { saleIsRefundable, saleIsRollbackable } from '../../utils/saleRefund';
import HelpHint from '../Shared/HelpHint';
import {
  saleAmountRefunded,
  saleAppliedPaid,
  saleChangeDue,
  saleFinalStatusLabel,
  saleHasRefundActivity,
  saleItemVariantLabel,
  saleNetBalanceDue,
  saleNetPaymentStatusLabel,
  normalizeSaleForReceipt,
} from '../../utils/saleItemDisplay';
import {
  SALE_AWAITING_APPROVAL_MESSAGE,
  saleIsAwaitingApproval,
  saleNeedsSalespersonAction,
  saleReceiptBlockedReason,
  saleRejectionReason,
  saleCanAdminReturnForCorrection,
  saleDateInputValue,
  saleMaxCorrectableDateInput,
  userCanCorrectSaleDate,
} from '../../utils/saleCompletionApproval';
import { salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { hasDuplicateSaleLines } from '../../utils/detectDuplicateSaleLines';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { resolveStoreName, resolveReceiptLogoUrl, DEFAULT_STORE_TAGLINE } from '../../utils/storeBranding';

export default function SaleDetailDialog({
  sale,
  open,
  onOpenChange,
  onRefund,
  canRefund = false,
  onRollback,
  canRollback = false,
  onPrint,
  canReturnForCorrection = false,
  onReturned,
  onUpdated,
  showCustomerName = true,
  showAdminDetails = true,
}) {
  const { settings } = useStoreSettings();
  const storeName = resolveStoreName(settings);
  const logoUrl = resolveReceiptLogoUrl(settings);
  const [showReturn, setShowReturn] = useState(false);
  const [returnReason, setReturnReason] = useState('');
  const [returning, setReturning] = useState(false);
  const [saleDate, setSaleDate] = useState(() => saleDateInputValue(sale?.occurred_at || sale?.created_at));
  const [savingDate, setSavingDate] = useState(false);

  useEffect(() => {
    setShowReturn(false);
    setReturnReason('');
    setSaleDate(saleDateInputValue(sale?.occurred_at || sale?.created_at));
  }, [sale?.id, sale?.occurred_at, sale?.created_at]);

  if (!sale) return null;

  const receiptSale = normalizeSaleForReceipt(sale);
  const finalStatus = saleFinalStatusLabel(sale);
  const duplicateLines = hasDuplicateSaleLines(sale.items);
  const refundedAmount = saleAmountRefunded(sale);
  const hasRefund = saleHasRefundActivity(sale);
  const balanceDue = saleNetBalanceDue(sale);
  const paymentStatus = saleNetPaymentStatusLabel(sale);
  const returnedToSalesperson = saleNeedsSalespersonAction(sale);
  const managerComment = saleRejectionReason(sale);
  const receiptBlocked = saleReceiptBlockedReason(sale);
  const canReturn = canReturnForCorrection && saleCanAdminReturnForCorrection(sale);
  const canCorrectDate =
    sale.status !== 'cancelled' &&
    (sale.can_correct_date === true || userCanCorrectSaleDate());
  const originalSaleDate = saleDateInputValue(sale.occurred_at || sale.created_at);
  const saleDateChanged = Boolean(saleDate) && saleDate !== originalSaleDate;

  const returnForCorrection = async () => {
    if (!returnReason.trim()) {
      toast.warning('Please say why you are returning this sale');
      return;
    }
    setReturning(true);
    try {
      const res = await salesAPI.rejectComplete(sale.id, {
        rejection_reason: returnReason.trim(),
      });
      toast.success('Sale returned to the salesperson for correction.');
      onReturned?.(res.data);
      onOpenChange(false);
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.error || data?.rejection_reason || data?.detail || 'Could not return this sale'
      );
    } finally {
      setReturning(false);
    }
  };

  const saveSaleDate = async () => {
    if (!saleDateChanged) return;
    setSavingDate(true);
    try {
      const res = await salesAPI.correctDate(sale.id, { occurred_on: saleDate });
      toast.success('Sale date updated. Daily sales, reports, and books follow the new date.');
      onUpdated?.(res.data);
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.error || data?.occurred_on || data?.occurred_at || data?.detail || 'Could not change the sale date'
      );
    } finally {
      setSavingDate(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5">
              <SaleChannelIcon channel={sale.client_channel} className="h-4 w-4" />
              <span>Sale — {sale.sale_number}</span>
            </span>
            {showAdminDetails && duplicateLines ? (
              <Badge variant="outline" className="text-xs text-amber-800 border-amber-300">
                Duplicate lines
              </Badge>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        {returnedToSalesperson ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm">
            <p className="font-semibold text-amber-950">Needs salesperson action</p>
            <p className="text-amber-900">
              This sale was returned. Fix it on POS and send it again. A sticky Daily note was also
              sent.
            </p>
            {managerComment ? (
              <p className="mt-1 text-amber-900">Manager comment: {managerComment}</p>
            ) : null}
          </div>
        ) : saleIsAwaitingApproval(sale) ? (
          <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-950">
            {SALE_AWAITING_APPROVAL_MESSAGE}
          </div>
        ) : null}

        <div className="receipt-content space-y-4 text-sm">
          <div className="receipt-header text-center">
            {logoUrl ? (
              <img src={logoUrl} alt="" className="mx-auto mb-2 h-16 w-16 object-contain" />
            ) : null}
            <h3 className="text-lg font-semibold">{storeName}</h3>
            <p className="text-xs text-muted-foreground">{DEFAULT_STORE_TAGLINE}</p>
            <p className="text-muted-foreground">Sale receipt</p>
          </div>

          <div className="receipt-info space-y-1">
            <p>
              <strong>Sale number:</strong> {sale.sale_number}
            </p>
            {saleChannelLabel(sale.client_channel) ? (
              <p className="inline-flex items-center gap-1.5">
                <strong>Recorded on:</strong>
                <SaleChannelIcon channel={sale.client_channel} />
                {saleChannelLabel(sale.client_channel)}
              </p>
            ) : null}
            <p>
              <strong>Date:</strong> {formatDateTime(sale.occurred_at || sale.created_at)}
            </p>
            {showCustomerName && sale.customer_name ? (
              <p>
                <strong>Customer:</strong> {sale.customer_name}
              </p>
            ) : null}
            <p>
              <strong>Cashier:</strong> {sale.cashier_name || 'N/A'}
            </p>
          </div>

          <div className="receipt-items overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                  <th className="pb-2 pr-2">Item</th>
                  <th className="pb-2 px-2 text-right">Qty</th>
                  <th className="pb-2 px-2 text-right">Price</th>
                  <th className="pb-2 pl-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {receiptSale.items?.length ? (
                  receiptSale.items.map((item) => {
                    const variantLabel = saleItemVariantLabel(item);
                    return (
                      <tr key={item.id} className="border-b border-dashed border-border/60">
                        <td className="py-2 pr-2">
                          <div>{item.product_name || item.product?.name || 'Item'}</div>
                          {variantLabel ? (
                            <div className="text-xs text-muted-foreground">{variantLabel}</div>
                          ) : null}
                        </td>
                        <td className="py-2 px-2 text-right tabular-nums">{item.quantity}</td>
                        <td className="py-2 px-2 text-right tabular-nums">
                          {formatCurrency(item.unit_price)}
                        </td>
                        <td className="py-2 pl-2 text-right tabular-nums">
                          {formatCurrency(item.subtotal)}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-muted-foreground">
                      No items on this sale.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="receipt-summary space-y-1 border-t pt-3">
            <SummaryRow label="Subtotal" value={formatCurrency(receiptSale.subtotal)} />
            {parseFloat(receiptSale.tax_amount) > 0 ? (
              <SummaryRow label="Tax" value={formatCurrency(receiptSale.tax_amount)} />
            ) : null}
            {parseFloat(receiptSale.discount_amount) > 0 ? (
              <SummaryRow
                label="Discount"
                value={`-${formatCurrency(receiptSale.discount_amount)}`}
              />
            ) : null}
            <SummaryRow label="Total" value={formatCurrency(receiptSale.total)} strong />
            <SummaryRow label="Payment method" value={sale.payment_method || '—'} />
            <SummaryRow label="Amount paid" value={formatCurrency(saleAppliedPaid(receiptSale))} />
            {saleChangeDue(receiptSale) > 0 ? (
              <SummaryRow label="Change" value={formatCurrency(saleChangeDue(receiptSale))} />
            ) : null}
          </div>

          {(sale.shipping_address || sale.shipping_location) && (
            <div className="space-y-1 border-t border-dashed pt-3">
              <p className="font-semibold">Shipping</p>
              {sale.delivery_method ? (
                <p className="text-muted-foreground">
                  <strong>Method:</strong>{' '}
                  {sale.delivery_method.charAt(0).toUpperCase() + sale.delivery_method.slice(1)}
                </p>
              ) : null}
              {sale.shipping_address ? (
                <p className="text-muted-foreground">
                  <strong>Address:</strong> {sale.shipping_address}
                </p>
              ) : null}
              {sale.shipping_location ? (
                <p className="text-muted-foreground">
                  <strong>Location:</strong> {sale.shipping_location}
                </p>
              ) : null}
              {parseFloat(receiptSale.delivery_cost) > 0 ? (
                <p className="text-muted-foreground">
                  <strong>Delivery cost:</strong> {formatCurrency(receiptSale.delivery_cost)}
                </p>
              ) : null}
            </div>
          )}

          {sale.notes ? (
            <div className="border-t border-dashed pt-3">
              <p>
                <strong>Notes:</strong> {sale.notes}
              </p>
            </div>
          ) : null}
        </div>

        {showAdminDetails ? (
          <div className="space-y-1 rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Admin
            </p>
            {sale.is_late_entry ? (
              <SummaryRow label="Late entry" value="Yes" className="text-amber-800" />
            ) : null}
            {sale.occurred_at ? (
              <SummaryRow label="Sale date" value={formatDateTime(sale.occurred_at)} />
            ) : null}
            <SummaryRow label="Recorded in system" value={formatDateTime(sale.created_at)} />
            {sale.served_by_name ? (
              <SummaryRow label="Served by" value={sale.served_by_name} />
            ) : null}
            {sale.backfill_reason ? (
              <SummaryRow label="Entry reason" value={sale.backfill_reason} />
            ) : null}
            {sale.backfill_receipt_photo_url ? (
              <div className="space-y-1 pt-1">
                <p className="text-muted-foreground">Paper receipt</p>
                <a
                  href={sale.backfill_receipt_photo_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block"
                >
                  <img
                    src={sale.backfill_receipt_photo_url}
                    alt="Paper receipt"
                    className="max-h-40 rounded border object-contain"
                  />
                </a>
              </div>
            ) : null}
            <SummaryRow label="Status" value={finalStatus} />
            <SummaryRow label="Payment status" value={paymentStatus} />
            {balanceDue > 0 ? (
              <SummaryRow
                label="Balance due"
                value={formatCurrency(balanceDue)}
                className="text-destructive"
              />
            ) : null}
            {hasRefund && refundedAmount > 0 ? (
              <SummaryRow
                label="Amount refunded"
                value={formatCurrency(refundedAmount)}
                className="text-amber-800"
              />
            ) : null}
            {parseFloat(sale.refundable_remaining) > 0 && sale.refund_status !== 'refunded' ? (
              <SummaryRow
                label="Still refundable"
                value={formatCurrency(sale.refundable_remaining)}
              />
            ) : null}
          </div>
        ) : null}

        {canCorrectDate ? (
          <div className="space-y-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <div className="flex items-center gap-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Sale date
              </p>
              <HelpHint actionKey="sale_correct_date" />
            </div>
            <p className="text-xs text-muted-foreground">
              Daily sales, reports, and the books use this date. The recorded time of day stays the same.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[10rem] flex-1">
                <Label htmlFor={`sale-date-${sale.id}`} className="sr-only">
                  Sale date
                </Label>
                <Input
                  id={`sale-date-${sale.id}`}
                  type="date"
                  value={saleDate}
                  max={saleMaxCorrectableDateInput()}
                  onChange={(e) => setSaleDate(e.target.value)}
                />
              </div>
              <Button
                type="button"
                onClick={saveSaleDate}
                disabled={!saleDateChanged || savingDate}
              >
                {savingDate ? 'Saving…' : 'Save date'}
              </Button>
            </div>
          </div>
        ) : null}

        {canReturn && showReturn ? (
          <div className="space-y-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
            <p className="font-semibold">Return this sale to the salesperson</p>
            <p className="text-muted-foreground">
              {sale.status === 'completed'
                ? 'Stock, journal, and accounting for this sale will be reversed. After they edit it, the sale goes through approval again before it can affect stock and books.'
                : 'The salesperson must change the sale, then send it for approval again.'}
            </p>
            <Label htmlFor={`return-sale-${sale.id}`}>Reason</Label>
            <Input
              id={`return-sale-${sale.id}`}
              value={returnReason}
              onChange={(event) => setReturnReason(event.target.value)}
              placeholder="Why should this sale be corrected?"
            />
            <Button
              size="sm"
              variant="destructive"
              onClick={returnForCorrection}
              disabled={returning}
            >
              {returning ? 'Returning…' : 'Confirm return'}
            </Button>
          </div>
        ) : null}

        <DialogFooter className="flex-wrap gap-2 sm:justify-between">
          <div className="flex flex-wrap items-center gap-1">
            {canRollback && saleIsRollbackable(sale) && onRollback ? (
              <span className="inline-flex items-center">
                <Button variant="destructive" onClick={() => onRollback(sale)}>
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Roll back sale
                </Button>
                <HelpHint actionKey="sale_rollback" />
              </span>
            ) : null}
            {canRefund && saleIsRefundable(sale) && onRefund ? (
              <span className="inline-flex items-center">
                <Button variant="destructive" onClick={() => onRefund(sale)}>
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Void / refund
                </Button>
                <HelpHint actionKey="sale_refund" />
              </span>
            ) : null}
            {canReturn ? (
              <span className="inline-flex items-center">
                <Button
                  variant="destructive"
                  onClick={() => setShowReturn((open) => !open)}
                  disabled={returning}
                >
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Return for correction
                </Button>
              </span>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            {onPrint && !receiptBlocked ? <Button onClick={onPrint}>Print receipt</Button> : null}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SummaryRow({ label, value, strong = false, className = '' }) {
  return (
    <div className={`flex justify-between gap-4 ${className}`}>
      <span className={strong ? 'font-semibold' : 'text-muted-foreground'}>{label}</span>
      <span className={strong ? 'font-semibold tabular-nums' : 'tabular-nums'}>{value}</span>
    </div>
  );
}
