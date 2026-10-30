import React from 'react';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../lib/cn';

/**
 * Sticky context for a sale returned for correction — reason, customer, and
 * original money snapshot so staff can fix without hunting.
 */
export default function CorrectionModePanel({
  notice,
  customer,
  originalSnapshot,
  className,
}) {
  if (!notice) return null;

  const phone = (customer?.phone || '').trim();
  const wallet = customer?.wallet_balance;
  const walletNum = wallet != null && wallet !== '' ? Number(wallet) : null;

  return (
    <div
      className={cn(
        'border-b border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950 sm:px-4',
        className,
      )}
      data-testid="returned-sale-banner"
      data-correction-mode="true"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <p className="font-semibold tracking-tight">
            Correction Mode · {notice.saleNumber}
          </p>
          <p className="text-xs text-amber-900/85">
            Fix lines or payment, then send this sale back for approval.
          </p>
        </div>
        {originalSnapshot ? (
          <div
            className="shrink-0 rounded-md border border-amber-200/80 bg-white/70 px-2.5 py-1.5 text-xs tabular-nums"
            data-testid="correction-original-snapshot"
          >
            <p className="font-medium text-amber-950">When returned</p>
            <p className="text-amber-900">
              {originalSnapshot.itemCount} item
              {originalSnapshot.itemCount === 1 ? '' : 's'} ·{' '}
              {formatCurrency(originalSnapshot.total)} · paid{' '}
              {formatCurrency(originalSnapshot.paid)}
              {originalSnapshot.paymentMethod
                ? ` · ${String(originalSnapshot.paymentMethod).toUpperCase()}`
                : ''}
            </p>
          </div>
        ) : null}
      </div>

      {notice.comment ? (
        <div className="mt-2 rounded-md border border-amber-200/70 bg-white/60 px-2.5 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-amber-800/80">
            Manager comment
          </p>
          <p className="mt-0.5 whitespace-pre-wrap text-sm text-amber-950">
            {notice.comment}
          </p>
        </div>
      ) : null}

      <div
        className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-amber-900"
        data-testid="correction-customer-card"
      >
        <span className="font-medium">
          Customer:{' '}
          {(customer?.name || '').trim() || 'Walk-in'}
        </span>
        {phone ? <span>Phone: {phone}</span> : null}
        {walletNum != null && Number.isFinite(walletNum) ? (
          <span>Wallet: {formatCurrency(walletNum)}</span>
        ) : null}
      </div>
    </div>
  );
}

/** Compact Was → Now money strip for the payment column. */
export function CorrectionTotalsCompare({ originalSnapshot, currentTotal, currentPaid }) {
  if (!originalSnapshot) return null;
  const wasTotal = Number(originalSnapshot.total) || 0;
  const wasPaid = Number(originalSnapshot.paid) || 0;
  const nowTotal = Number(currentTotal) || 0;
  const nowPaid = Number(currentPaid) || 0;
  const totalChanged = Math.abs(wasTotal - nowTotal) > 0.009;
  const paidChanged = Math.abs(wasPaid - nowPaid) > 0.009;

  return (
    <div
      className="rounded-md border border-amber-200/80 bg-amber-50/80 px-2.5 py-2 text-xs"
      data-testid="correction-totals-compare"
    >
      <p className="mb-1 font-medium text-amber-950">Was → Now</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 tabular-nums text-amber-900">
        <span className="text-muted-foreground">Total</span>
        <span className={totalChanged ? 'font-semibold text-amber-950' : ''}>
          {formatCurrency(wasTotal)} → {formatCurrency(nowTotal)}
        </span>
        <span className="text-muted-foreground">Paid</span>
        <span className={paidChanged ? 'font-semibold text-amber-950' : ''}>
          {formatCurrency(wasPaid)} → {formatCurrency(nowPaid)}
        </span>
      </div>
    </div>
  );
}
