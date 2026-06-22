import React from 'react';
import { Clock } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/cn';
import { formatCurrency } from '../../utils/formatters';
import {
  ACCOUNT_PAYMENT_HINT,
  ACCOUNT_PAYMENT_LABEL,
  computeAccountBalanceDue,
  isFullPayLater,
} from '../../utils/accountPayment';

/**
 * Checkbox + pay-later action + balance preview for POS / billing checkout.
 */
export function AccountPaymentBlock({
  visible = false,
  checked = false,
  onCheckedChange,
  hasRegisteredCustomer = false,
  total = 0,
  amountPaid,
  onPayFullAmountLater,
  className,
  customerHintId = 'account-payment-hint',
}) {
  if (!visible) return null;

  const paid = parseFloat(amountPaid);
  const paidN = Number.isFinite(paid) ? paid : checked ? 0 : null;
  const showBalance =
    checked && hasRegisteredCustomer && paidN !== null && paidN < total;
  const fullLater = showBalance && isFullPayLater(total, paidN);

  return (
    <div className={cn('space-y-2 rounded-lg border border-slate-100 bg-slate-50/90 px-3 py-3', className)}>
      <label className="flex cursor-pointer items-start gap-2.5 text-sm leading-snug">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 shrink-0"
          checked={checked}
          onChange={(e) => {
            if (typeof onCheckedChange === 'function') {
              onCheckedChange(e.target.checked);
            }
          }}
          aria-describedby={customerHintId}
        />
        <span>{ACCOUNT_PAYMENT_LABEL}</span>
      </label>

      {!hasRegisteredCustomer ? (
        <p id={customerHintId} className="text-xs leading-relaxed text-muted-foreground">
          Select or add a registered customer to charge a balance to their account.
        </p>
      ) : (
        <p id={customerHintId} className="text-xs leading-relaxed text-muted-foreground">
          {ACCOUNT_PAYMENT_HINT}
        </p>
      )}

      {checked && hasRegisteredCustomer ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full gap-2"
          onClick={() => {
            if (typeof onPayFullAmountLater === 'function') {
              onPayFullAmountLater();
            }
          }}
        >
          <Clock className="h-4 w-4" />
          Pay full amount later
        </Button>
      ) : null}

      {showBalance ? (
        <div className="rounded-md border border-amber-200/80 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          {fullLater ? (
            <p>
              <span className="font-medium">Pay later:</span> entire{' '}
              <span className="font-semibold tabular-nums">{formatCurrency(total)}</span> will be
              added to the customer account.
            </p>
          ) : (
            <p>
              <span className="font-medium">Balance on account:</span>{' '}
              <span className="font-semibold tabular-nums">
                {formatCurrency(computeAccountBalanceDue(total, paidN))}
              </span>
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default AccountPaymentBlock;
