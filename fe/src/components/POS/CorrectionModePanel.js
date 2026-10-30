import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import { Button } from '../ui/button';

/**
 * Compact Correction Mode chrome — stays out of the way of the cart.
 * Expanded details (comment, snapshot) are optional so editing is never blocked.
 */
export default function CorrectionModePanel({
  notice,
  customer,
  originalSnapshot,
  className,
  defaultExpanded = false,
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  if (!notice) return null;

  const phone = (customer?.phone || '').trim();
  const wallet = customer?.wallet_balance;
  const walletNum = wallet != null && wallet !== '' ? Number(wallet) : null;
  const customerLabel = (customer?.name || '').trim() || 'Walk-in';
  const comment = String(notice.comment || '').trim();

  return (
    <div
      className={cn(
        'border-b border-amber-300/80 bg-amber-100/90 text-amber-950',
        className,
      )}
      data-testid="returned-sale-banner"
      data-correction-mode="true"
    >
      <div className="flex items-center gap-2 px-3 py-2 sm:px-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold tracking-tight">
            Rectify · {notice.saleNumber}
            <span className="ml-2 font-normal text-amber-900/80">
              {customerLabel}
              {phone ? ` · ${phone}` : ''}
            </span>
          </p>
          <p className="truncate text-[11px] text-amber-900/75">
            {comment
              ? comment
              : 'Edit cart or payment, then send back for approval.'}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-8 shrink-0 px-2 text-amber-950 hover:bg-amber-200/60"
          aria-expanded={expanded}
          data-testid="correction-details-toggle"
          onClick={() => setExpanded((open) => !open)}
        >
          Details
          <ChevronDown
            className={cn(
              'ml-1 h-3.5 w-3.5 transition-transform',
              expanded ? 'rotate-180' : '',
            )}
            aria-hidden
          />
        </Button>
      </div>

      {expanded ? (
        <div
          className="space-y-2 border-t border-amber-200/80 bg-amber-50/90 px-3 py-2.5 sm:px-4"
          data-testid="correction-details"
        >
          {comment ? (
            <div className="rounded-md border border-amber-200/70 bg-white/70 px-2.5 py-2">
              <p className="text-[11px] font-medium uppercase tracking-wide text-amber-800/80">
                Manager comment
              </p>
              <p className="mt-0.5 whitespace-pre-wrap text-sm text-amber-950">
                {comment}
              </p>
            </div>
          ) : null}

          {originalSnapshot ? (
            <div
              className="rounded-md border border-amber-200/80 bg-white/70 px-2.5 py-1.5 text-xs tabular-nums"
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

          <div
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-amber-900"
            data-testid="correction-customer-card"
          >
            <span className="font-medium">Customer: {customerLabel}</span>
            {phone ? <span>Phone: {phone}</span> : null}
            {walletNum != null && Number.isFinite(walletNum) ? (
              <span>Wallet: {formatCurrency(walletNum)}</span>
            ) : null}
          </div>
        </div>
      ) : null}
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
      className="rounded-md border border-amber-300/70 bg-amber-50 px-2.5 py-2 text-xs"
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
