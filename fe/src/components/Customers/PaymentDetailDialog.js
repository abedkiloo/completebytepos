import React from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import ReceiptImageLink from '../Shared/ReceiptImageLink';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { customerDetailPath, formatDebtTrail } from '../../utils/customerDetail';
import {
  settlementMethodLabel,
  settlementPayerLabel,
  settlementReferenceLabel,
} from '../../utils/debtManagement';

const KIND_LABELS = {
  debt_settlement: 'Debt collection',
  invoice_payment: 'Invoice payment',
  sale_payment: 'Sale tender',
};

function DetailRow({ label, children }) {
  if (children == null || children === '' || children === '—') return null;
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-foreground">{children}</dd>
    </div>
  );
}

/**
 * Read-only payment detail — same idea as SaleDetailDialog for settlements
 * and other money-in rows after they have been received.
 *
 * @param {object} props
 * @param {object|null} props.payment Trail / collection / ledger row.
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {boolean} [props.canCorrect=false]
 * @param {() => void} [props.onCorrect]
 * @param {boolean} [props.loading=false]
 */
export default function PaymentDetailDialog({
  payment,
  open,
  onOpenChange,
  canCorrect = false,
  onCorrect,
  loading = false,
}) {
  if (!payment && !loading) return null;

  const kind =
    payment?.kind ||
    (payment?.source_type === 'debt_settlement' ? 'debt_settlement' : '') ||
    'debt_settlement';
  const kindLabel = KIND_LABELS[kind] || 'Payment';
  const when = payment?.occurred_at || payment?.created_at;
  const receivedBy = payment?.received_by || payment?.created_by_name || '—';
  const debtTrail = kind === 'debt_settlement' ? formatDebtTrail(payment) : '';
  const paidTowards = payment?.paid_towards || [];
  const saleId =
    payment?.sale_id ||
    payment?.sale ||
    paidTowards.find((t) => t?.sale_id)?.sale_id ||
    null;
  const saleNumber =
    payment?.sale_number ||
    paidTowards.find((t) => t?.sale_number)?.sale_number ||
    null;
  const invoiceId =
    paidTowards.find((t) => t?.invoice_id)?.invoice_id || null;
  const invoiceNumber =
    paidTowards.find((t) => t?.invoice_number)?.invoice_number || null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] max-w-lg overflow-y-auto"
        data-testid="payment-detail-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            Payment detail
            <Badge variant="secondary" className="text-[10px] font-normal">
              {kindLabel}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {loading || !payment ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Loading payment…
          </p>
        ) : (
          <div className="space-y-5">
            <div className="rounded-md border bg-muted/30 px-3 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Amount received
              </p>
              <p
                className="mt-1 text-2xl font-semibold tabular-nums text-success"
                data-testid="payment-detail-amount"
              >
                {formatCurrency(payment.amount)}
              </p>
              {when ? (
                <p className="mt-1 text-sm text-muted-foreground">
                  {formatDateTime(when)}
                  {payment.is_backdated ? ' · Backdated' : ''}
                </p>
              ) : null}
            </div>

            <dl className="space-y-2.5">
              <DetailRow label="Customer">
                {payment.customer_id ? (
                  <Link
                    to={customerDetailPath(payment.customer_id, { tab: 'ledger' })}
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                    onClick={() => onOpenChange?.(false)}
                  >
                    {payment.customer_name || 'Customer'}
                    <ExternalLink className="h-3 w-3" aria-hidden />
                  </Link>
                ) : (
                  payment.customer_name || null
                )}
                {[payment.customer_phone, payment.customer_code].filter(Boolean).length ? (
                  <div className="text-xs text-muted-foreground">
                    {[payment.customer_phone, payment.customer_code]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                ) : null}
              </DetailRow>
              <DetailRow label="Method">{settlementMethodLabel(payment)}</DetailRow>
              <DetailRow label="Paid by">
                {kind === 'debt_settlement' ? settlementPayerLabel(payment) : null}
              </DetailRow>
              <DetailRow label="Reference">
                <span className="font-mono">{settlementReferenceLabel(payment)}</span>
              </DetailRow>
              <DetailRow label="Collected by">{receivedBy}</DetailRow>
              <DetailRow label="Notes">{(payment.notes || '').trim() || null}</DetailRow>
              {debtTrail ? <DetailRow label="Balance trail">{debtTrail}</DetailRow> : null}
              {saleNumber || saleId ? (
                <DetailRow label="Related sale">
                  {saleId ? (
                    <span className="text-muted-foreground">
                      {saleNumber || `Sale #${saleId}`}
                      <span className="ml-1 text-xs">(open from Sales for full receipt)</span>
                    </span>
                  ) : (
                    saleNumber
                  )}
                </DetailRow>
              ) : null}
              {invoiceNumber || invoiceId ? (
                <DetailRow label="Invoice">
                  {invoiceNumber || `Invoice #${invoiceId}`}
                </DetailRow>
              ) : null}
            </dl>

            {paidTowards.length > 0 ? (
              <div className="space-y-2 border-t pt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Paid towards
                </p>
                <p className="text-sm font-medium">
                  {payment.paid_towards_label || '—'}
                </p>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {paidTowards.map((t, idx) => (
                    <li key={`${t.type}-${t.sale_id || t.invoice_id || idx}`}>
                      {t.label}
                      {t.amount ? ` · ${formatCurrency(t.amount)}` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {payment.receipt_image_url ? (
              <div className="space-y-2 border-t pt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Payment screenshot
                </p>
                <ReceiptImageLink
                  url={payment.receipt_image_url}
                  label="Payment screenshot"
                  variant="card"
                />
              </div>
            ) : (
              <p className="border-t pt-3 text-sm text-muted-foreground">
                No payment screenshot attached.
              </p>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <div>
            {canCorrect && onCorrect && kind === 'debt_settlement' ? (
              <Button
                type="button"
                variant="outline"
                onClick={onCorrect}
                data-testid="payment-detail-correct"
              >
                Correct amount
              </Button>
            ) : null}
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => onOpenChange?.(false)}
            data-testid="payment-detail-close"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
