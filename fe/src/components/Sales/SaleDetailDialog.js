import React from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { saleIsRefundable, refundStatusLabel } from '../../utils/saleRefund';
import {
  saleBalanceDue,
  saleItemVariantLabel,
  salePaymentStatusLabel,
} from '../../utils/saleItemDisplay';
import { hasDuplicateSaleLines } from '../../utils/detectDuplicateSaleLines';

export default function SaleDetailDialog({
  sale,
  open,
  onOpenChange,
  onRefund,
  canRefund = false,
  onPrint,
  showCustomerName = true,
}) {
  if (!sale) return null;

  const balanceDue = saleBalanceDue(sale);
  const paymentStatus = salePaymentStatusLabel(sale);
  const refundLabel = refundStatusLabel(sale.refund_status);
  const duplicateLines = hasDuplicateSaleLines(sale.items);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span>Sale — {sale.sale_number}</span>
            {refundLabel ? (
              <Badge variant="secondary" className="text-xs">
                {refundLabel}
              </Badge>
            ) : null}
            {duplicateLines ? (
              <Badge variant="outline" className="text-xs text-amber-800 border-amber-300">
                Duplicate lines
              </Badge>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        <div className="receipt-content space-y-4 text-sm">
          <div className="receipt-header text-center">
            <h3 className="text-lg font-semibold">CompleteByte POS</h3>
            <p className="text-muted-foreground">Sale receipt</p>
          </div>

          <div className="receipt-info space-y-1">
            <p>
              <strong>Sale number:</strong> {sale.sale_number}
            </p>
            <p>
              <strong>Date:</strong> {formatDateTime(sale.created_at)}
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
                {sale.items?.map((item) => {
                  const variantLabel = saleItemVariantLabel(item);
                  const refunded = parseInt(item.quantity_refunded, 10) || 0;
                  return (
                    <tr key={item.id} className="border-b border-dashed border-border/60">
                      <td className="py-2 pr-2">
                        <div>{item.product_name || item.product?.name || 'Item'}</div>
                        {variantLabel ? (
                          <div className="text-xs text-muted-foreground">{variantLabel}</div>
                        ) : null}
                        {refunded > 0 ? (
                          <div className="text-xs text-amber-700">
                            {refunded} of {item.quantity} refunded
                          </div>
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
                })}
              </tbody>
            </table>
          </div>

          <div className="receipt-summary space-y-1 border-t pt-3">
            <SummaryRow label="Subtotal" value={formatCurrency(sale.subtotal)} />
            {parseFloat(sale.tax_amount) > 0 ? (
              <SummaryRow label="Tax" value={formatCurrency(sale.tax_amount)} />
            ) : null}
            {parseFloat(sale.discount_amount) > 0 ? (
              <SummaryRow label="Discount" value={`-${formatCurrency(sale.discount_amount)}`} />
            ) : null}
            <SummaryRow label="Total" value={formatCurrency(sale.total)} strong />
            <SummaryRow label="Payment method" value={sale.payment_method || '—'} />
            <SummaryRow label="Amount paid" value={formatCurrency(sale.amount_paid)} />
            <SummaryRow label="Payment status" value={paymentStatus} />
            {balanceDue > 0 ? (
              <SummaryRow
                label="Balance due"
                value={formatCurrency(balanceDue)}
                className="text-destructive"
              />
            ) : null}
            {parseFloat(sale.change) > 0 ? (
              <SummaryRow label="Change" value={formatCurrency(sale.change)} />
            ) : null}
            {parseFloat(sale.amount_refunded) > 0 ? (
              <SummaryRow
                label="Amount refunded"
                value={formatCurrency(sale.amount_refunded)}
                className="text-amber-800"
              />
            ) : null}
            {parseFloat(sale.refundable_remaining) > 0 &&
            sale.refund_status !== 'refunded' ? (
              <SummaryRow
                label="Refundable remaining"
                value={formatCurrency(sale.refundable_remaining)}
              />
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
              {parseFloat(sale.delivery_cost) > 0 ? (
                <p className="text-muted-foreground">
                  <strong>Delivery cost:</strong> {formatCurrency(sale.delivery_cost)}
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

        <DialogFooter className="flex-wrap gap-2 sm:justify-between">
          <div>
            {canRefund && saleIsRefundable(sale) && onRefund ? (
              <Button variant="destructive" onClick={() => onRefund(sale)}>
                <RotateCcw className="mr-1 h-4 w-4" />
                Void / Refund
              </Button>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            {onPrint ? <Button onClick={onPrint}>Print receipt</Button> : null}
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
