import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { customersAPI } from '../../services/api';
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
 * Move a posted debt repayment onto the customer who paid.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.collection Settlement row. Needs id and amount.
 * @param {() => void} [props.onSaved]
 */
export default function TransferCollectionCustomerDialog({
  open,
  onOpenChange,
  collection,
  onSaved,
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [moveSales, setMoveSales] = useState(true);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setMatches([]);
    setChosen(null);
    setMoveSales(true);
    setReason('');
  }, [open, collection]);

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
          const currentId = collection?.customer_id || collection?.customer;
          setMatches(
            (Array.isArray(rows) ? rows : []).filter(
              (row) => String(row.id) !== String(currentId)
            ).slice(0, 8)
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
  }, [open, query, collection]);

  if (!collection) return null;

  const submit = async (e) => {
    e.preventDefault();
    if (!chosen?.id) {
      toast.error('Choose the customer who should have this repayment');
      return;
    }
    setBusy(true);
    try {
      await customersAPI.transferWalletSettlementCustomer(collection.id, {
        customer_id: chosen.id,
        move_sales: moveSales,
        reason: reason.trim(),
      });
      toast.success(
        moveSales
          ? 'Repayment and its sales moved to the correct customer'
          : 'Repayment moved to the correct customer'
      );
      onOpenChange?.(false);
      onSaved?.();
    } catch (err) {
      const detail =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'Could not move this repayment';
      toast.error(typeof detail === 'string' ? detail : 'Could not move this repayment');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Move repayment to the correct customer</DialogTitle>
          <DialogDescription>
            {formatCurrency(collection.amount)} is on{' '}
            {collection.customer_name || 'the current customer'}. Choose who
            actually paid. The amount is not changed.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="transfer-customer-search">Correct customer</Label>
            <Input
              id="transfer-customer-search"
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
              checked={moveSales}
              onChange={(e) => setMoveSales(e.target.checked)}
              disabled={busy}
              data-testid="transfer-move-sales"
            />
            <span>
              Also move the sales this repayment paid onto that customer.
              Leave this off when the sales are already on the right customer
              and only the repayment was keyed wrong.
            </span>
          </label>
          <div className="space-y-2">
            <Label htmlFor="transfer-customer-reason">Reason (optional)</Label>
            <Input
              id="transfer-customer-reason"
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
              Move repayment
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
