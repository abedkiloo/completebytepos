import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { customersAPI, salesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

/**
 * Move one completed sale onto the customer it was for.
 *
 * Payments stay on the customer they were keyed to. An admin can choose
 * to text the correct customer.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.sale Completed sale. Needs id.
 * @param {(sale: object) => void} [props.onSaved]
 */
export default function TransferSaleCustomerDialog({
  open,
  onOpenChange,
  sale,
  onSaved,
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [sendSms, setSendSms] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setMatches([]);
    setChosen(null);
    setSendSms(false);
    setReason('');
  }, [open, sale]);

  useEffect(() => {
    if (!open) return undefined;
    const term = query.trim();
    if (term.length < 2) {
      setMatches([]);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await customersAPI.list({
          search: term,
          is_active: 'true',
          page_size: 8,
        });
        const rows = res.data?.results || res.data || [];
        if (!cancelled) {
          const currentId = sale?.customer_id || sale?.customer;
          setMatches(
            (Array.isArray(rows) ? rows : [])
              .filter((row) => String(row.id) !== String(currentId))
              .slice(0, 8)
          );
        }
      } catch {
        if (!cancelled) setMatches([]);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, query, sale]);

  if (!sale) return null;

  const submit = async (e) => {
    e.preventDefault();
    if (!chosen?.id) {
      toast.error('Choose the customer this sale was for');
      return;
    }
    setBusy(true);
    try {
      const res = await salesAPI.transferCustomer(sale.id, {
        customer_id: chosen.id,
        send_sms: sendSms,
        reason: reason.trim(),
      });
      const smsNote = sendSms && !res?.data?.sms_sent ? ' SMS was not sent.' : '';
      toast.success(`Sale moved to ${chosen.name}.${smsNote}`);
      onOpenChange?.(false);
      onSaved?.(res.data);
    } catch (err) {
      const detail =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'Could not move this sale';
      toast.error(typeof detail === 'string' ? detail : 'Could not move this sale');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Move this sale to the correct customer</DialogTitle>
          <DialogDescription>
            {sale.sale_number} ({formatCurrency(sale.total)}) moves with the
            money paid at the counter. A payment recorded later stays on the
            original customer. Move that later payment from Debt Management.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="transfer-sale-customer-search">Correct customer</Label>
            <Input
              id="transfer-sale-customer-search"
              value={chosen ? chosen.name : query}
              onChange={(e) => {
                setChosen(null);
                setQuery(e.target.value);
              }}
              placeholder="Type the customer name"
              autoComplete="off"
              disabled={busy}
            />
            {matches.length > 0 && !chosen ? (
              <ul className="max-h-40 overflow-auto rounded-md border">
                {matches.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                      onClick={() => {
                        setChosen({ id: row.id, name: row.name });
                        setMatches([]);
                      }}
                    >
                      {row.name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={sendSms}
              onChange={(e) => setSendSms(e.target.checked)}
              disabled={busy}
              data-testid="sale-transfer-send-sms"
            />
            <span>Send an SMS to the correct customer about this sale.</span>
          </label>
          <div className="space-y-2">
            <Label htmlFor="transfer-sale-reason">Reason (optional)</Label>
            <Input
              id="transfer-sale-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={200}
              disabled={busy}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange?.(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !chosen}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Move this sale
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
