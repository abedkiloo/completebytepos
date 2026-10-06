import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MessageSquareText, RefreshCw } from 'lucide-react';

import { messagingAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeader,
  DataTableRow,
} from '../page';

function smsPartsHint(chars) {
  const n = Number(chars) || 0;
  if (n <= 160) return '1 SMS part';
  if (n <= 306) return '~2 SMS parts';
  return 'Long message';
}

export default function DebtReminderDialog({ open, onOpenChange }) {
  const [template, setTemplate] = useState('');
  const [preview, setPreview] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [saveTemplate, setSaveTemplate] = useState(true);

  const loadPreview = useCallback(async (body) => {
    setLoading(true);
    try {
      const res = await messagingAPI.debtReminderPreview({
        template: body || undefined,
      });
      const data = res.data || {};
      setPreview(data);
      if (body == null && data.template) {
        setTemplate(data.template);
      }
      const ids = new Set((data.recipients || []).map((r) => r.customer_id));
      setSelected(ids);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not load debtor list');
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setSaveTemplate(true);
    loadPreview(null);
  }, [open, loadPreview]);

  const recipients = preview?.recipients || [];
  const selectedRecipients = useMemo(
    () => recipients.filter((r) => selected.has(r.customer_id)),
    [recipients, selected],
  );
  const selectedDebt = useMemo(
    () =>
      selectedRecipients.reduce((sum, r) => sum + (Number(r.amount) || 0), 0),
    [selectedRecipients],
  );
  const sample = selectedRecipients[0] || recipients[0];

  const toggleAll = (checked) => {
    if (checked) {
      setSelected(new Set(recipients.map((r) => r.customer_id)));
    } else {
      setSelected(new Set());
    }
  };

  const toggleOne = (id, checked) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleRefreshPreview = async () => {
    await loadPreview(template);
  };

  const handleSend = async () => {
    if (selected.size === 0) {
      toast.error('Select at least one debtor');
      return;
    }
    setSending(true);
    try {
      const res = await messagingAPI.debtReminderSend({
        template,
        customer_ids: Array.from(selected),
        save_template: saveTemplate,
      });
      const queued = res.data?.queued ?? selected.size;
      toast.success(`Sent ${queued} reminder${queued === 1 ? '' : 's'}`);
      onOpenChange(false);
    } catch (err) {
      const data = err?.response?.data;
      const msg =
        data?.sms ||
        data?.recipients ||
        data?.detail ||
        (typeof data === 'object' ? Object.values(data).flat?.()?.[0] : null) ||
        'Send failed';
      toast.error(typeof msg === 'string' ? msg : 'Send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl"
        description="Review debtors, edit the SMS template, then send personalized reminders."
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquareText className="h-5 w-5" />
            Weekly debt reminders
          </DialogTitle>
          <DialogDescription>
            Suggested Monday routine: generate the list, verify numbers and amounts,
            soft-edit the message, then send. Each customer gets their own name and balance
            via Mobile Sasa personalized bulk.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="debt-sms-template" className="text-sm font-medium">
                Message template
              </label>
              <p className="text-xs text-muted-foreground">
                Placeholders: {'{name}'} · {'{amount}'} · {'{store_name}'}
              </p>
            </div>
            <textarea
              id="debt-sms-template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={saveTemplate}
                  onChange={(e) => setSaveTemplate(e.target.checked)}
                />
                Save as default template
              </label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleRefreshPreview}
                disabled={loading}
              >
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                Refresh preview
              </Button>
              {sample ? (
                <Badge variant="secondary">{smsPartsHint(sample.message_chars)}</Badge>
              ) : null}
            </div>
          </div>

          {sample ? (
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Sample to {sample.greeting_name}
              </p>
              <p className="mt-1 text-sm leading-relaxed">{sample.message}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>
              <strong>{selected.size}</strong> of {recipients.length} selected
            </span>
            <span className="text-muted-foreground">
              {formatCurrency(selectedDebt)} outstanding
            </span>
            {preview?.skipped_no_phone > 0 ? (
              <span className="text-amber-700 dark:text-amber-400">
                {preview.skipped_no_phone} skipped (no phone)
              </span>
            ) : null}
          </div>

          <div className="max-h-64 overflow-auto rounded-md border">
            <DataTable>
              <DataTableHeader>
                <DataTableRow>
                  <DataTableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label="Select all debtors"
                      checked={
                        recipients.length > 0 && selected.size === recipients.length
                      }
                      onChange={(e) => toggleAll(e.target.checked)}
                    />
                  </DataTableHead>
                  <DataTableHead>Duka / name</DataTableHead>
                  <DataTableHead>Phone</DataTableHead>
                  <DataTableHead align="right">Debt</DataTableHead>
                </DataTableRow>
              </DataTableHeader>
              <DataTableBody>
                {loading && recipients.length === 0 ? (
                  <DataTableRow>
                    <DataTableCell colSpan={4}>Loading debtors…</DataTableCell>
                  </DataTableRow>
                ) : null}
                {!loading && recipients.length === 0 ? (
                  <DataTableRow>
                    <DataTableCell colSpan={4}>
                      No debtors with a phone number right now.
                    </DataTableCell>
                  </DataTableRow>
                ) : null}
                {recipients.map((r) => (
                  <DataTableRow key={r.customer_id}>
                    <DataTableCell>
                      <input
                        type="checkbox"
                        checked={selected.has(r.customer_id)}
                        onChange={(e) => toggleOne(r.customer_id, e.target.checked)}
                        aria-label={`Select ${r.greeting_name}`}
                      />
                    </DataTableCell>
                    <DataTableCell>
                      <div className="font-medium">{r.greeting_name}</div>
                      {r.name && r.name !== r.greeting_name ? (
                        <div className="text-xs text-muted-foreground">{r.name}</div>
                      ) : null}
                    </DataTableCell>
                    <DataTableCell className="tabular-nums">{r.phone}</DataTableCell>
                    <DataTableCell align="right" className="tabular-nums">
                      {formatCurrency(r.amount)}
                    </DataTableCell>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSend}
            disabled={sending || selected.size === 0 || loading}
          >
            {sending ? 'Sending…' : `Send to ${selected.size}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
