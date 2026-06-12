import React, { useState, useEffect, useMemo } from 'react';
import {
  Receipt as ReceiptIcon,
  Loader2,
  Truck,
  Percent,
  AlertTriangle,
} from 'lucide-react';

import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Separator } from '../../ui/separator';
import { formatCurrency } from '../../../utils/formatters';
import { cn } from '../../../lib/cn';
import {
  filterEnabledPaymentMethods,
  paymentReferenceLabel,
  paymentReferencePlaceholder,
  paymentReferenceRequired,
} from '../../../utils/paymentMethods';

export function CheckoutPanel({
  // totals
  subtotal,
  discount,
  discountAmount,
  setDiscount,
  discountType,
  setDiscountType,
  taxPct,
  setTaxPct,
  taxAmount,
  total,
  change,

  // delivery
  deliveryEnabled,
  setDeliveryEnabled,
  deliveryCost,
  setDeliveryCost,

  // payment
  paymentMethod,
  setPaymentMethod,
  receivedAmount,
  setReceivedAmount,
  paymentReference,
  setPaymentReference,

  // submit
  submitting,
  onPay,

  // misc
  itemCount,
  hasOversell = false,
  enabledPaymentMethods,
  showDiscount = true,
  showTax = true,
  showDelivery = true,
}) {
  const [showExtras, setShowExtras] = useState(false);
  const methods = useMemo(
    () => filterEnabledPaymentMethods(enabledPaymentMethods),
    [enabledPaymentMethods]
  );

  useEffect(() => {
    if (!methods.some((m) => m.id === paymentMethod)) {
      setPaymentMethod(methods[0]?.id || 'cash');
    }
  }, [methods, paymentMethod, setPaymentMethod]);

  useEffect(() => {
    if (!paymentReferenceRequired(paymentMethod)) {
      setPaymentReference('');
    }
  }, [paymentMethod, setPaymentReference]);

  const method = methods.find((m) => m.id === paymentMethod) || methods[0];

  const isCashLike = method.requiresAmount;
  const needsReference = paymentReferenceRequired(paymentMethod);
  const referenceOk = !needsReference || String(paymentReference || '').trim().length > 0;
  const canPay =
    !hasOversell &&
    itemCount > 0 &&
    total > 0 &&
    referenceOk &&
    (!isCashLike || parseFloat(receivedAmount) > 0);

  return (
    <div className="flex flex-col border-t bg-background">
      {/* Totals */}
      <div className="space-y-1 px-3 py-2 text-sm">
        <Row label="Subtotal" value={formatCurrency(subtotal)} />
        {showDiscount && discountAmount > 0 && (
          <Row label="Discount" value={`- ${formatCurrency(discountAmount)}`} muted />
        )}
        {showTax && taxAmount > 0 && (
          <Row label={`Tax (${taxPct}%)`} value={formatCurrency(taxAmount)} muted />
        )}
        {showDelivery && deliveryEnabled && deliveryCost > 0 && (
          <Row label="Delivery" value={formatCurrency(deliveryCost)} muted />
        )}

        {(showDiscount || showTax || showDelivery) && (
        <button
          type="button"
          onClick={() => setShowExtras((v) => !v)}
          className="text-xs font-medium text-primary hover:underline"
        >
          {showExtras ? 'Hide' : 'Add'}{' '}
          {[showDiscount && 'discount', showTax && 'tax', showDelivery && 'delivery']
            .filter(Boolean)
            .join(' / ')}
        </button>
        )}

        {showExtras && (showDiscount || showTax || showDelivery) && (
          <div className="mt-2 grid grid-cols-2 gap-2">
            {showDiscount && (
            <div className="col-span-2 flex items-center gap-2">
              <Percent className="h-4 w-4 text-muted-foreground" />
              <Input
                type="number"
                min="0"
                step="0.01"
                value={discount || ''}
                onChange={(e) => setDiscount(parseFloat(e.target.value) || 0)}
                placeholder="Discount"
                className="h-9"
              />
              <ToggleSegment
                value={discountType}
                onChange={setDiscountType}
                options={[
                  { value: 'percentage', label: '%' },
                  { value: 'flat', label: 'KES' },
                ]}
              />
            </div>
            )}

            {showTax && (
            <div className="flex items-center gap-2">
              <Percent className="h-4 w-4 text-muted-foreground" />
              <Input
                type="number"
                min="0"
                step="0.01"
                value={taxPct || ''}
                onChange={(e) => setTaxPct(parseFloat(e.target.value) || 0)}
                placeholder="Tax %"
                className="h-9"
              />
            </div>
            )}

            {showDelivery && (
            <div className="flex items-center gap-2">
              <Truck className="h-4 w-4 text-muted-foreground" />
              <Input
                type="number"
                min="0"
                step="0.01"
                value={deliveryEnabled ? deliveryCost || '' : ''}
                onFocus={() => setDeliveryEnabled(true)}
                onChange={(e) => {
                  const v = parseFloat(e.target.value) || 0;
                  setDeliveryCost(v);
                  setDeliveryEnabled(v > 0);
                }}
                placeholder="Delivery cost"
                className="h-9"
              />
            </div>
            )}
          </div>
        )}
      </div>

      <Separator />

      {/* Grand total */}
      <div className="flex items-baseline justify-between px-3 py-2">
        <span className="text-sm font-medium text-muted-foreground">Total</span>
        <span className="text-pos-total tabular-nums">{formatCurrency(total)}</span>
      </div>

      <Separator />

      {/* Payment method tabs */}
      <div className="px-3 pt-2">
        <Label className="mb-1 block text-xs uppercase tracking-wide text-muted-foreground">
          Payment method
        </Label>
        <div
          className={cn(
            'grid gap-1',
            methods.length <= 2 ? 'grid-cols-2' : methods.length === 3 ? 'grid-cols-3' : 'grid-cols-4'
          )}
        >
          {methods.map((m) => {
            const Icon = m.icon;
            const active = paymentMethod === m.id;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => setPaymentMethod(m.id)}
                className={cn(
                  'pos-target flex flex-col items-center justify-center gap-0.5 rounded-md border py-2 text-xs font-medium transition-colors',
                  active
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background text-foreground hover:bg-accent'
                )}
              >
                <Icon className="h-5 w-5" />
                <span>{m.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {needsReference ? (
        <div className="px-3 pt-2">
          <Label
            htmlFor="payment-reference"
            className="mb-1 block text-xs uppercase tracking-wide text-muted-foreground"
          >
            {paymentReferenceLabel(paymentMethod)} *
          </Label>
          <Input
            id="payment-reference"
            type="text"
            value={paymentReference}
            onChange={(e) => setPaymentReference(e.target.value)}
            placeholder={paymentReferencePlaceholder(paymentMethod)}
            className="h-10 font-mono text-sm"
            autoComplete="off"
          />
        </div>
      ) : null}

      {/* Cash / M-Pesa: amount tendered + quick-cash */}
      {isCashLike && (
        <div className="px-3 pt-2">
          <Label htmlFor="received" className="mb-1 block text-xs uppercase tracking-wide text-muted-foreground">
            Amount received
          </Label>
          <Input
            id="received"
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            value={receivedAmount}
            onChange={(e) => setReceivedAmount(e.target.value)}
            placeholder="0.00"
            className="h-11 text-right text-lg font-semibold tabular-nums"
            autoComplete="off"
          />

          {change > 0 && (
            <div className="mt-2 flex items-center justify-between rounded-md bg-success/10 px-3 py-2">
              <span className="text-sm font-medium text-success">Change due</span>
              <span className="text-base font-semibold tabular-nums text-success">
                {formatCurrency(change)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Oversell warning — visible above the Pay button so the cashier
          immediately understands why the button is disabled. */}
      {hasOversell && (
        <div className="mx-4 mt-3 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            One or more items exceed available stock. Reduce the quantity in the
            cart to continue.
          </span>
        </div>
      )}

      {/* Pay button — the primary CTA */}
      <div className="p-3 pt-2">
        <Button
          size="cashier-lg"
          className="w-full text-base font-semibold"
          onClick={onPay}
          disabled={!canPay || submitting}
        >
          {submitting ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Processing…
            </>
          ) : (
            <>
              <ReceiptIcon className="h-5 w-5" />
              Complete sale · {formatCurrency(total)}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

function Row({ label, value, muted = false }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className={cn('text-sm', muted ? 'text-muted-foreground' : 'text-foreground')}>
        {label}
      </span>
      <span className="text-sm font-medium tabular-nums">{value}</span>
    </div>
  );
}

function ToggleSegment({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-md border bg-background">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'h-9 min-w-[2.5rem] px-2.5 text-xs font-medium',
            value === opt.value
              ? 'bg-primary text-primary-foreground'
              : 'text-foreground hover:bg-accent'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
