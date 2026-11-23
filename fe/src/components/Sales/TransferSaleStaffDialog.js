import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { salesAPI } from '../../services/api';
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
 * Move one completed sale from one salesperson to another.
 *
 * Only an admin opens this. The customer, the amount, and the stock stay.
 * Commission follows the new person. A locked pay for that month refuses the move.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {object|null} props.sale Completed sale. Needs id.
 * @param {(sale: object) => void} [props.onSaved]
 */
export default function TransferSaleStaffDialog({
  open,
  onOpenChange,
  sale,
  onSaved,
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setMatches([]);
    setChosen(null);
    setReason('');
  }, [open, sale]);

  useEffect(() => {
    if (!open) return undefined;
    const term = query.trim();
    if (term.length < 1) {
      setMatches([]);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await salesAPI.staffChoices(term);
        const rows = Array.isArray(res.data) ? res.data : [];
        if (!cancelled) {
          const currentId = sale?.served_by || sale?.cashier;
          setMatches(
            rows
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

  const submit = async () => {
    if (!sale?.id || !chosen?.id) {
      toast.error('Choose the salesperson who should have this sale.');
      return;
    }
    setBusy(true);
    try {
      await salesAPI.transferStaff(sale.id, {
        user_id: chosen.id,
        reason: reason.trim(),
      });
      toast.success(`This sale is now with ${chosen.display_name}.`);
      onSaved?.();
    } catch (error) {
      const message = error.response?.data?.error || 'Could not move this sale.';
      toast.error(typeof message === 'string' ? message : 'Could not move this sale.');
    } finally {
      setBusy(false);
    }
  };

  const currentName = sale?.served_by_name || sale?.cashier_name || 'the current salesperson';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Move this sale to another salesperson</DialogTitle>
          <DialogDescription>
            {sale?.sale_number ? `${sale.sale_number} is with ${currentName}. ` : ''}
            The customer, the amount, and the stock stay. Commission and sales by person follow the new salesperson. If that month’s pay is already locked, the sale stays put.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1">
            <Label htmlFor="sale-staff-search">Salesperson</Label>
            <Input
              id="sale-staff-search"
              data-testid="sale-staff-search"
              value={query}
              placeholder="Name"
              onChange={(event) => {
                setQuery(event.target.value);
                setChosen(null);
              }}
            />
          </div>
          {matches.length > 0 && (
            <div className="grid gap-1">
              {matches.map((row) => (
                <Button
                  key={row.id}
                  type="button"
                  variant={chosen?.id === row.id ? 'default' : 'outline'}
                  onClick={() => setChosen(row)}
                >
                  {row.display_name}
                </Button>
              ))}
            </div>
          )}
          <div className="grid gap-1">
            <Label htmlFor="sale-staff-reason">Note (optional)</Label>
            <Input
              id="sale-staff-reason"
              value={reason}
              maxLength={200}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" data-testid="sale-staff-move" disabled={busy || !chosen} onClick={submit}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
            Move to this salesperson
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
