import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import {
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
} from '../../utils/makerChecker';
import {
  collectionPayerDetailsEnabled,
  mpesaDestinationLabel,
  MPESA_DESTINATION_OPTIONS,
  validateCollectionPayerFields,
} from '../../utils/collectionPayer';
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
  isLiveMpesaPrompt,
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
];

const todayLocalDate = () => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const EMPTY_FORM = {
  amount: '',
  payment_method: 'cash',
  reference: '',
  notes: '',
  payer_name: '',
  payer_phone: '',
  mpesa_destination: '',
  payment_date: todayLocalDate(),
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
  const [mpesaMode, setMpesaMode] = useState(MPESA_CAPTURE_CODE);
  const [mpesaPhone, setMpesaPhone] = useState('');
  const [stkOpen, setStkOpen] = useState(false);
  const [receiptFile, setReceiptFile] = useState(null);
  const [receiptPreview, setReceiptPreview] = useState(null);

  const debtAmount = getWalletDebtAmount(customer?.wallet_balance);
  const { permissions } = getStoredAuth();
  const canApproveCollection = hasPermission(permissions, 'debt_management', 'approve');
  const requirePayer = collectionPayerDetailsEnabled();
  const needsDestinationBeforeCode =
    requirePayer &&
    form.payment_method === 'mpesa' &&
    !isLiveMpesaPrompt(mpesaMode);
  const codeUnlocked =
    !needsDestinationBeforeCode || Boolean(form.mpesa_destination);

  useEffect(() => {
    if (!open || !customer?.id) {
      setForm({ ...EMPTY_FORM, payment_date: todayLocalDate() });
      setTransactions([]);
      setFieldErrors({});
      setMpesaMode(MPESA_CAPTURE_CODE);
      setMpesaPhone('');
      setStkOpen(false);
      setReceiptFile(null);
      setReceiptPreview(null);
      return;
    }
    setForm({
      ...EMPTY_FORM,
      payment_date: todayLocalDate(),
      amount: debtAmount > 0 ? String(debtAmount) : '',
      payer_name: customer.name || '',
      payer_phone: customer.phone || '',
    });
    setMpesaMode(MPESA_CAPTURE_CODE);
    setMpesaPhone(customer.phone || '');
    setReceiptFile(null);
    setReceiptPreview(null);

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
  }, [open, customer?.id, debtAmount, customer?.name, customer?.phone]);

  const updateField = (key, value) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'payment_method' && value !== 'mpesa') {
        next.mpesa_destination = '';
      }
      if (key === 'mpesa_destination' && !value) {
        next.reference = '';
      }
      return next;
    });
    setFieldErrors((prev) => {
      if (
        !prev[key] &&
        !(key === 'payment_method' && (prev.reference || prev.mpesa_destination))
      ) {
        return prev;
      }
      const next = { ...prev };
      delete next[key];
      if (key === 'payment_method') {
        delete next.reference;
        delete next.mpesa_destination;
      }
      if (key === 'mpesa_destination') delete next.reference;
      return next;
    });
  };

  const onReceiptSelected = (file) => {
    if (receiptPreview && typeof URL !== 'undefined' && URL.revokeObjectURL) {
      URL.revokeObjectURL(receiptPreview);
    }
    if (!file) {
      setReceiptFile(null);
      setReceiptPreview(null);
      return;
    }
    setReceiptFile(file);
    const preview =
      typeof URL !== 'undefined' && URL.createObjectURL
        ? URL.createObjectURL(file)
        : null;
    setReceiptPreview(preview);
    setFieldErrors((prev) => {
      if (!prev.receipt_image) return prev;
      const next = { ...prev };
      delete next.receipt_image;
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
      if (!receiptFile) {
        errors.receipt_image = 'Attach a screenshot of the M-Pesa repayment receipt.';
      }
      if (isLiveMpesaPrompt(mpesaMode)) {
        const phoneErr = phoneMessage(mpesaPhone, { required: true });
        if (phoneErr) errors.phone = phoneErr;
      } else {
        if (needsDestinationBeforeCode && !form.mpesa_destination) {
          errors.mpesa_destination =
            'Say whether this M-Pesa code came via till or bank before entering the code.';
        } else {
          const codeError = mpesaReceiptMessage(form.reference);
          if (codeError) errors.reference = codeError;
        }
      }
    }
    if (form.payment_date && form.payment_date > todayLocalDate()) {
      errors.payment_date = 'Payment date cannot be in the future.';
    }
    if (requirePayer) {
      Object.assign(
        errors,
        validateCollectionPayerFields({
          paymentMethod: form.payment_method,
          reference: form.reference,
          payerName: form.payer_name,
          payerPhone: form.payer_phone,
          mpesaDestination: form.mpesa_destination,
          requirePayer: true,
          requireMpesaDestinationForCode:
            form.payment_method === 'mpesa' && !isLiveMpesaPrompt(mpesaMode),
        })
      );
    }
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      toast.error(
        errors.amount ||
          errors.receipt_image ||
          errors.payment_date ||
          errors.payer_name ||
          errors.payer_phone ||
          errors.mpesa_destination ||
          errors.reference ||
          errors.phone
      );
      return;
    }
    setPendingAmount(parsePaymentAmount(form.amount));
    setShowCommitConfirm(true);
  };

  const recordPayment = async (referenceValue) => {
    if (!customer?.id || submitting || pendingAmount == null) return;
    setSubmitting(true);
    try {
      const fields = {
        amount: pendingAmount,
        payment_method: form.payment_method,
        reference:
          form.payment_method === 'mpesa'
            ? normalizeMpesaReceipt(referenceValue)
            : String(referenceValue || '').trim(),
        notes: form.notes.trim(),
      };
      if (form.payment_date && form.payment_date !== todayLocalDate()) {
        fields.payment_date = form.payment_date;
      }
      if (requirePayer) {
        fields.payer_name = form.payer_name.trim();
        fields.payer_phone = form.payer_phone.trim();
        fields.mpesa_destination =
          form.payment_method === 'mpesa' ? form.mpesa_destination || '' : '';
      }

      let payload = fields;
      if (receiptFile) {
        const body = new FormData();
        Object.entries(fields).forEach(([key, value]) => {
          if (value === null || value === undefined) return;
          body.append(key, String(value));
        });
        body.append('receipt_image', receiptFile);
        payload = body;
      }

      const res = await customersAPI.receiveWalletPayment(customer.id, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(pendingApprovalToastMessage());
        setShowCommitConfirm(false);
        setPendingAmount(null);
        setStkOpen(false);
        onSuccess?.(customer);
        onOpenChange(false);
        return;
      }
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
      const data = error.response?.data || {};
      const msg =
        data.error ||
        data.receipt_image?.[0] ||
        data.payment_date?.[0] ||
        data.payer_name?.[0] ||
        data.payer_phone?.[0] ||
        data.mpesa_destination?.[0] ||
        data.amount?.[0] ||
        data.detail ||
        error.message ||
        'Failed to record payment';
      toast.error(msg);
      setShowCommitConfirm(false);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmCommit = async () => {
    if (form.payment_method === 'mpesa' && isLiveMpesaPrompt(mpesaMode)) {
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
          requirePayer && form.payer_name.trim()
            ? { label: 'Paid by', value: form.payer_name.trim() }
            : null,
          requirePayer && form.payer_phone.trim()
            ? { label: 'Payer phone', value: form.payer_phone.trim() }
            : null,
          form.payment_method === 'mpesa' && form.mpesa_destination
            ? {
                label: 'M-Pesa via',
                value: mpesaDestinationLabel(form.mpesa_destination),
              }
            : null,
          form.payment_method === 'mpesa' && isLiveMpesaPrompt(mpesaMode)
            ? { label: 'Phone', value: mpesaPhone }
            : form.reference.trim()
            ? {
                label: form.payment_method === 'mpesa' ? 'M-Pesa code' : 'Reference',
                value: form.reference.trim(),
              }
            : null,
          form.payment_date && form.payment_date !== todayLocalDate()
            ? { label: 'Payment date', value: form.payment_date }
            : null,
          receiptFile ? { label: 'Receipt', value: receiptFile.name || 'Attached' } : null,
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
            account. {canApproveCollection
              ? 'This reduces POS debt or adds wallet credit.'
              : 'A manager will approve this before the wallet is updated.'}
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

          {requirePayer ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="wallet-payer-name">Who paid *</Label>
                <Input
                  id="wallet-payer-name"
                  value={form.payer_name}
                  onChange={(e) => updateField('payer_name', e.target.value)}
                  placeholder="Name of the person who paid"
                  aria-invalid={Boolean(fieldErrors.payer_name)}
                  data-testid="wallet-payer-name"
                />
                {fieldErrors.payer_name ? (
                  <p className="text-xs text-destructive">{fieldErrors.payer_name}</p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="wallet-payer-phone">Payer phone *</Label>
                <Input
                  id="wallet-payer-phone"
                  type="tel"
                  inputMode="tel"
                  value={form.payer_phone}
                  onChange={(e) => updateField('payer_phone', e.target.value)}
                  placeholder="07… or +254…"
                  aria-invalid={Boolean(fieldErrors.payer_phone)}
                  data-testid="wallet-payer-phone"
                />
                {fieldErrors.payer_phone ? (
                  <p className="text-xs text-destructive">{fieldErrors.payer_phone}</p>
                ) : null}
              </div>
            </div>
          ) : null}

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
              <>
                {needsDestinationBeforeCode ? (
                  <div className="space-y-2" data-testid="mpesa-destination-step">
                    <Label>Did the payment come via till or bank? *</Label>
                    <div className="grid grid-cols-2 gap-1">
                      {MPESA_DESTINATION_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          data-testid={`mpesa-destination-${opt.value}`}
                          disabled={submitting}
                          onClick={() => updateField('mpesa_destination', opt.value)}
                          className={
                            form.mpesa_destination === opt.value
                              ? 'rounded-md border border-primary bg-primary/10 px-2 py-2 text-xs font-medium text-primary'
                              : 'rounded-md border border-border bg-background px-2 py-2 text-xs font-medium hover:bg-accent'
                          }
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                    {fieldErrors.mpesa_destination ? (
                      <p className="text-xs text-destructive">
                        {fieldErrors.mpesa_destination}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Choose till or bank first, then enter the M-Pesa code.
                      </p>
                    )}
                  </div>
                ) : null}
                {codeUnlocked ? (
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
                ) : null}
              </>
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
                  Optional for cash.
                </p>
                {fieldErrors.reference ? (
                  <p className="text-xs text-destructive">{fieldErrors.reference}</p>
                ) : null}
              </>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wallet-payment-date">Payment date *</Label>
            <Input
              id="wallet-payment-date"
              type="date"
              max={todayLocalDate()}
              value={form.payment_date}
              onChange={(e) => updateField('payment_date', e.target.value)}
              aria-invalid={Boolean(fieldErrors.payment_date)}
              data-testid="wallet-payment-date"
            />
            {form.payment_date && form.payment_date !== todayLocalDate() ? (
              <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
                Marked as a past repayment on {form.payment_date} (not today).
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Use today for payments received now. Change the date only when
                recording a repayment from an earlier day.
              </p>
            )}
            {fieldErrors.payment_date ? (
              <p className="text-xs text-destructive">{fieldErrors.payment_date}</p>
            ) : null}
          </div>

          {form.payment_method === 'mpesa' ? (
            <div className="space-y-2">
              <Label htmlFor="wallet-receipt-image">M-Pesa receipt screenshot *</Label>
              <Input
                id="wallet-receipt-image"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                onChange={(e) => onReceiptSelected(e.target.files?.[0] || null)}
                aria-invalid={Boolean(fieldErrors.receipt_image)}
                data-testid="wallet-receipt-image"
              />
              <p className="text-xs text-muted-foreground">
                Upload a clear screenshot of the M-Pesa confirmation (JPEG, PNG, WebP, or GIF, max 5 MB).
              </p>
              {receiptPreview ? (
                <img
                  src={receiptPreview}
                  alt="M-Pesa receipt preview"
                  className="max-h-40 rounded-md border object-contain"
                />
              ) : null}
              {fieldErrors.receipt_image ? (
                <p className="text-xs text-destructive">{fieldErrors.receipt_image}</p>
              ) : null}
            </div>
          ) : null}

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
      description={
        canApproveCollection
          ? 'Do you really want to continue with this transaction? This records the payment on the customer account.'
          : 'Do you really want to continue with this transaction? A manager must approve it before the wallet is updated.'
      }
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
