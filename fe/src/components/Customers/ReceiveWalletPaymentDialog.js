import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
import { toast } from '../../utils/toast';
import { CustomerWalletBalance } from './CustomerWalletBalance';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import CommitConfirm from '../Shared/CommitConfirm';
import MpesaCapture from '../Payments/MpesaCapture';
import StkWaitDialog from '../Payments/StkWaitDialog';
import {
  MPESA_CAPTURE_CODE,
  MPESA_CAPTURE_PROMPT,
} from '../../utils/mpesaCapture';
import {
  AMOUNT_EXAMPLE,
  paymentAmountMessage,
  parsePaymentAmount,
  mpesaReceiptMessage,
  normalizeMpesaReceipt,
  phoneMessage,
} from '../../utils/formValidation';

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'mpesa', label: 'M-PESA' },
  { value: 'card', label: 'Card' },
  { value: 'other', label: 'Other' },
];

const EMPTY_FORM = {
  amount: '',
  payment_method: 'cash',
  reference: '',
  notes: '',
};

/**
 * Record a standalone payment against customer wallet debt (negative balance).
 * Mirrors the invoice payment flow but credits the customer wallet.
 */
export default function ReceiveWalletPaymentDialog({
  open,
  customer,
  onOpenChange,
  onSuccess,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [loadingTxns, setLoadingTxns] = useState(false);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const [pendingAmount, setPendingAmount] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [mpesaMode, setMpesaMode] = useState(MPESA_CAPTURE_PROMPT);
  const [mpesaPhone, setMpesaPhone] = useState('');
  const [stkOpen, setStkOpen] = useState(false);

  const debtAmount = getWalletDebtAmount(customer?.wallet_balance);

  useEffect(() => {
    if (!open || !customer?.id) {
      setForm(EMPTY_FORM);
      setTransactions([]);
      setFieldErrors({});
      setMpesaMode(MPESA_CAPTURE_PROMPT);
      setMpesaPhone('');
      setStkOpen(false);
      return;
    }
    setForm((prev) => ({
      ...EMPTY_FORM,
      amount: debtAmount > 0 ? String(debtAmount) : prev.amount,
    }));
    setMpesaMode(MPESA_CAPTURE_PROMPT);
    setMpesaPhone(customer.phone || '');

    let cancelled = false;
    setLoadingTxns(true);
    customersAPI
      .walletTransactions(customer.id, { limit: 8 })
      .then((res) => {
        if (!cancelled) setTransactions(res.data || []);
      })
      .catch(() => {
        if (!cancelled) setTransactions([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingTxns(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, customer?.id, debtAmount]);

  const updateField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!prev[key] && !(key === 'payment_method' && prev.reference)) return prev;
      const next = { ...prev };
      delete next[key];
      if (key === 'payment_method') delete next.reference;
      return next;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!customer?.id || submitting) return;

    const errors = {};
    const amountError = paymentAmountMessage(form.amount);
    if (amountError) errors.amount = amountError;
    if (form.payment_method === 'mpesa') {
      if (mpesaMode === MPESA_CAPTURE_CODE) {
        const codeError = mpesaReceiptMessage(form.reference);
        if (codeError) errors.reference = codeError;
      } else {
        const phoneErr = phoneMessage(mpesaPhone, { required: true });
        if (phoneErr) errors.phone = phoneErr;
      }
    }
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      toast.error(errors.amount || errors.reference || errors.phone);
      return;
    }
    setPendingAmount(parsePaymentAmount(form.amount));
    setShowCommitConfirm(true);
  };

  const recordPayment = async (referenceValue) => {
    if (!customer?.id || submitting || pendingAmount == null) return;
    setSubmitting(true);
    try {
      const res = await customersAPI.receiveWalletPayment(customer.id, {
        amount: pendingAmount,
        payment_method: form.payment_method,
        reference:
          form.payment_method === 'mpesa'
            ? normalizeMpesaReceipt(referenceValue)
            : String(referenceValue || '').trim(),
        notes: form.notes.trim(),
      });
      toast.success('Payment recorded');
      setShowCommitConfirm(false);
      setPendingAmount(null);
      setStkOpen(false);
      onSuccess?.({
        ...customer,
        wallet_balance: res.data.wallet_balance,
      });
      onOpenChange(false);
    } catch (error) {
      const msg =
        error.response?.data?.error ||
        error.response?.data?.amount?.[0] ||
        error.response?.data?.detail ||
        error.message ||
        'Failed to record payment';
      toast.error(msg);
      setShowCommitConfirm(false);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmCommit = async () => {
    if (form.payment_method === 'mpesa' && mpesaMode === MPESA_CAPTURE_PROMPT) {
      setShowCommitConfirm(false);
      setStkOpen(true);
      return;
    }
    await recordPayment(form.reference);
  };

  const methodLabel =
    PAYMENT_METHODS.find((m) => m.value === form.payment_method)?.label || form.payment_method;
  const commitRows =
    pendingAmount == null
      ? []
      : [
          { label: 'Customer', value: customer?.name || '—' },
          {
            label: 'Amount',
            value: formatCurrency(pendingAmount),
            tone: 'success',
            emphasis: true,
          },
          { label: 'Method', value: methodLabel },
          form.payment_method === 'mpesa' && mpesaMode === MPESA_CAPTURE_PROMPT
            ? { label: 'Phone', value: mpesaPhone }
            : form.reference.trim()
            ? {
                label: form.payment_method === 'mpesa' ? 'M-Pesa code' : 'Reference',
                value: form.reference.trim(),
              }
            : null,
          debtAmount > 0
            ? { label: 'Current debt', value: formatCurrency(debtAmount) }
            : null,
        ].filter(Boolean);

  if (!customer) return null;

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" description="Record payment against customer wallet debt.">
        <DialogHeader>
          <DialogTitle>Receive wallet payment</DialogTitle>
          <DialogDescription>
            Apply a payment to <strong className="text-foreground">{customer.name}</strong>'s
            account. This reduces POS debt or adds wallet credit.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1 rounded-lg border bg-muted/30 p-4 text-sm">
          <p>
            <span className="text-muted-foreground">Wallet balance: </span>
            <CustomerWalletBalance balance={customer.wallet_balance} showZero />
          </p>
          {debtAmount > 0 && (
            <p>
              <span className="text-muted-foreground">Amount owed: </span>
              <span className="font-semibold text-destructive tabular-nums">
                {formatCurrency(debtAmount)}
              </span>
            </p>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="wallet-payment-amount">Payment amount *</Label>
            <div className="flex flex-wrap gap-2">
              <Input
                id="wallet-payment-amount"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={(e) => updateField('amount', e.target.value)}
                placeholder={AMOUNT_EXAMPLE}
                aria-invalid={Boolean(fieldErrors.amount)}
                className="min-w-[12rem] flex-1"
                required
              />
              {debtAmount > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => updateField('amount', String(debtAmount))}
                >
                  Pay full debt
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              KES amount with up to 2 decimal places, e.g. {AMOUNT_EXAMPLE}
            </p>
            {fieldErrors.amount ? (
              <p className="text-xs text-destructive">{fieldErrors.amount}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wallet-payment-method">Payment method *</Label>
            <select
              id="wallet-payment-method"
              value={form.payment_method}
              onChange={(e) => updateField('payment_method', e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            {form.payment_method === 'mpesa' ? (
              <MpesaCapture
                mode={mpesaMode}
                onModeChange={(next) => {
                  setMpesaMode(next);
                  setFieldErrors((prev) => {
                    if (!prev.reference && !prev.phone) return prev;
                    const nextErrors = { ...prev };
                    delete nextErrors.reference;
                    delete nextErrors.phone;
                    return nextErrors;
                  });
                }}
                phone={mpesaPhone}
                onPhoneChange={setMpesaPhone}
                code={form.reference}
                onCodeChange={(value) => updateField('reference', value)}
                disabled={submitting}
                showErrors={Boolean(fieldErrors.reference || fieldErrors.phone)}
              />
            ) : (
              <>
                <Label htmlFor="wallet-payment-reference">Reference</Label>
                <Input
                  id="wallet-payment-reference"
                  value={form.reference}
                  onChange={(e) => updateField('reference', e.target.value)}
                  placeholder="Receipt or payment reference (optional)"
                  aria-invalid={Boolean(fieldErrors.reference)}
                />
                <p className="text-xs text-muted-foreground">
                  Optional for cash; required for card.
                </p>
                {fieldErrors.reference ? (
                  <p className="text-xs text-destructive">{fieldErrors.reference}</p>
                ) : null}
              </>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wallet-payment-notes">Notes</Label>
            <Input
              id="wallet-payment-notes"
              value={form.notes}
              onChange={(e) => updateField('notes', e.target.value)}
              placeholder="Optional internal note"
            />
          </div>

          {(loadingTxns || transactions.length > 0) && (
            <div className="rounded-lg border bg-background p-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Recent wallet activity
              </p>
              {loadingTxns ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading…
                </div>
              ) : (
                <ul className="max-h-32 space-y-1 overflow-y-auto text-xs">
                  {transactions.map((txn) => (
                    <li key={txn.id} className="flex justify-between gap-2">
                      <span className="truncate text-muted-foreground">
                        {txn.source_type.replace(/_/g, ' ')}
                        {txn.sale_number ? ` · ${txn.sale_number}` : ''}
                      </span>
                      <span className="shrink-0 tabular-nums">
                        {txn.transaction_type === 'debit' ? '−' : '+'}
                        {formatCurrency(txn.amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Record payment
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    <CommitConfirm
      open={showCommitConfirm}
      onOpenChange={(next) => {
        if (!next && !submitting) {
          setShowCommitConfirm(false);
          setPendingAmount(null);
        }
      }}
      title="Proceed with this payment?"
      description="Do you really want to continue with this transaction? This records the payment on the customer account."
      rows={commitRows}
      submitting={submitting}
      confirmText="Yes, record payment"
      onConfirm={confirmCommit}
      variant="info"
    />
    <StkWaitDialog
      open={stkOpen}
      onOpenChange={setStkOpen}
      amount={pendingAmount || 0}
      phone={mpesaPhone}
      purpose="debt"
      customerId={customer.id}
      customerName={customer.name}
      onPaid={(paid) => {
        const receipt = paid?.mpesa_receipt || paid?.invoice_number || '';
        setForm((prev) => ({ ...prev, reference: receipt }));
        recordPayment(receipt);
      }}
    />
    </>
  );
}
