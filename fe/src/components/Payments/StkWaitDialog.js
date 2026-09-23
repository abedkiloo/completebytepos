import React, { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { paymentIntentsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';

function intentError(err, fallback) {
  return (
    err?.response?.data?.error ||
    err?.response?.data?.detail ||
    err?.response?.data?.phone?.[0] ||
    err?.message ||
    fallback
  );
}

/**
 * Create an STK intent, prompt the handset, and wait until Daraja confirms paid.
 */
export default function StkWaitDialog({
  open,
  onOpenChange,
  amount,
  phone,
  purpose = 'pos',
  customerId,
  customerName = '',
  onPaid,
}) {
  const [intent, setIntent] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const startedForOpen = useRef(false);

  useEffect(() => {
    if (!open) {
      startedForOpen.current = false;
      setIntent(null);
      setError('');
      setBusy(false);
      return undefined;
    }
    if (startedForOpen.current) return undefined;
    startedForOpen.current = true;

    let cancelled = false;
    (async () => {
      setBusy(true);
      setError('');
      try {
        const created = await paymentIntentsAPI.create({
          amount: Number(amount).toFixed(2),
          phone,
          purpose,
          customer_id: customerId || undefined,
          customer_name: customerName || undefined,
        });
        if (cancelled) return;
        let next = created.data;
        const prompted = await paymentIntentsAPI.stk(next.id);
        if (cancelled) return;
        next = prompted.data;
        setIntent(next);
      } catch (err) {
        if (!cancelled) setError(intentError(err, 'Could not send M-Pesa prompt.'));
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, amount, phone, purpose, customerId, customerName]);

  useEffect(() => {
    const id = intent?.id;
    const status = intent?.status;
    if (!open || !id || !status || ['paid', 'failed', 'cancelled', 'expired'].includes(status)) {
      return undefined;
    }
    const timer = setInterval(async () => {
      try {
        const res = await paymentIntentsAPI.get(id);
        setIntent(res.data);
      } catch {
        /* keep waiting */
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [open, intent?.id, intent?.status]);

  const paid = intent?.status === 'paid';
  const failed = ['failed', 'cancelled', 'expired'].includes(intent?.status);

  const handleQuery = async () => {
    if (!intent?.id) return;
    setBusy(true);
    try {
      const res = await paymentIntentsAPI.query(intent.id);
      setIntent(res.data);
    } catch (err) {
      setError(intentError(err, 'Could not check payment status.'));
    } finally {
      setBusy(false);
    }
  };

  const handleDone = () => {
    if (paid) {
      onPaid?.(intent);
    }
    onOpenChange(false);
  };

  let title = 'Waiting for M-Pesa';
  let body = `We asked ${phone} to pay ${formatCurrency(amount)}. Money is real only when confirmed.`;
  if (paid) {
    title = 'Payment confirmed';
    body = intent.mpesa_receipt
      ? `M-Pesa code ${intent.mpesa_receipt} confirmed.`
      : 'M-Pesa confirmed on the server.';
  } else if (failed) {
    title = 'Payment not completed';
    body = intent?.failure_reason || 'Customer cancelled or the prompt expired.';
  } else if (error && !intent) {
    title = 'Could not send prompt';
    body = error;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent description={body}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
        </DialogHeader>
        {(busy || (intent && !paid && !failed)) && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Waiting for the PIN prompt…
          </div>
        )}
        {error && intent ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}
        <DialogFooter>
          {!paid && !failed && intent ? (
            <Button type="button" variant="outline" onClick={handleQuery} disabled={busy}>
              Check status
            </Button>
          ) : null}
          <Button type="button" onClick={handleDone} disabled={busy && !intent}>
            {paid ? 'Use this payment' : 'Close'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
