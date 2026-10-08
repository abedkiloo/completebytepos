import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MessageSquareText, RefreshCw } from 'lucide-react';

import { customersAPI, messagingAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import SearchableSelect from '../Shared/SearchableSelect';
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

/**
 * Send any SMS template to all registered customers with a valid phone, or one.
 */
export default function CustomerSmsBlastDialog({
  open,
  onOpenChange,
  templates = [],
  initialTemplateKey = '',
}) {
  const templateOptions = useMemo(
    () =>
      (templates || []).map((t) => ({
        id: t.key,
        name: t.label || t.key,
      })),
    [templates],
  );

  const [templateKey, setTemplateKey] = useState('');
  const [template, setTemplate] = useState('');
  const [offer, setOffer] = useState('');
  const [scope, setScope] = useState('all');
  const [oneCustomerId, setOneCustomerId] = useState('');
  const [customerOptions, setCustomerOptions] = useState([]);
  const [preview, setPreview] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [saveTemplate, setSaveTemplate] = useState(true);

  const selectedSpec = useMemo(
    () => (templates || []).find((t) => t.key === templateKey) || null,
    [templates, templateKey],
  );
  const showOffer = Boolean(
    selectedSpec?.placeholders?.some((p) => p === '{offer}' || p === 'offer'),
  );

  const loadCustomerOptions = useCallback(async (term = '') => {
    try {
      const res = await customersAPI.list({
        search: term || undefined,
        is_active: 'true',
        page_size: 30,
      });
      const rows = res.data?.results || (Array.isArray(res.data) ? res.data : []);
      setCustomerOptions(
        rows.map((c) => ({
          id: String(c.id),
          name: `${c.name || c.owner_name || `Customer ${c.id}`}${
            c.phone ? ` · ${c.phone}` : ' · no phone'
          }`,
        })),
      );
    } catch {
      setCustomerOptions([]);
    }
  }, []);

  const loadPreview = useCallback(
    async ({
      key = templateKey,
      body = template,
      offerLine = offer,
      audience = scope,
      oneId = oneCustomerId,
    } = {}) => {
      if (!key) return;
      if (audience === 'one' && !oneId) {
        setPreview({ recipients: [], count: 0, skipped_no_phone: 0, skipped_invalid_phone: 0 });
        setSelected(new Set());
        return;
      }
      setLoading(true);
      try {
        const payload = {
          template_key: key,
          template: body || undefined,
          offer: offerLine != null ? offerLine : undefined,
          scope: audience,
        };
        if (audience === 'one') {
          payload.customer_id = Number(oneId);
        }
        const res = await messagingAPI.blastPreview(payload);
        const data = res.data || {};
        setPreview(data);
        if (data.template && body == null) {
          setTemplate(data.template);
        } else if (data.template && !body) {
          setTemplate(data.template);
        }
        const ids = new Set((data.recipients || []).map((r) => r.customer_id));
        setSelected(ids);
      } catch (err) {
        toast.error(err?.response?.data?.detail || err?.response?.data?.template_key || 'Could not load preview');
        setPreview(null);
      } finally {
        setLoading(false);
      }
    },
    [templateKey, template, offer, scope, oneCustomerId],
  );

  useEffect(() => {
    if (!open) return;
    setSaveTemplate(true);
    setOffer('');
    setScope('all');
    setOneCustomerId('');
    setSelected(new Set());
    const key =
      initialTemplateKey ||
      templateOptions.find((t) => t.id === 'promo_customer_week')?.id ||
      templateOptions[0]?.id ||
      '';
    setTemplateKey(key);
    const spec = (templates || []).find((t) => t.key === key);
    setTemplate(spec?.body || '');
    loadCustomerOptions('');
  }, [open, initialTemplateKey, templateOptions, templates, loadCustomerOptions]);

  useEffect(() => {
    if (!open || !templateKey) return;
    loadPreview({
      key: templateKey,
      body: template || undefined,
      offerLine: offer,
      audience: scope,
      oneId: oneCustomerId,
    });
    // Intentionally when audience / template key changes — not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, templateKey, scope, oneCustomerId]);

  const recipients = preview?.recipients || [];
  const selectedRecipients = useMemo(
    () => recipients.filter((r) => selected.has(r.customer_id)),
    [recipients, selected],
  );
  const sample = selectedRecipients[0] || recipients[0];

  const toggleAll = (checked) => {
    if (checked) setSelected(new Set(recipients.map((r) => r.customer_id)));
    else setSelected(new Set());
  };

  const toggleOne = (id, checked) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleRefreshPreview = () =>
    loadPreview({
      key: templateKey,
      body: template,
      offerLine: offer,
      audience: scope,
      oneId: oneCustomerId,
    });

  const handleSend = async () => {
    if (!templateKey) {
      toast.error('Pick a message template');
      return;
    }
    if (scope === 'one' && !oneCustomerId) {
      toast.error('Pick one customer');
      return;
    }
    if (scope === 'all' && selected.size === 0) {
      toast.error('Select at least one customer');
      return;
    }
    setSending(true);
    try {
      const payload = {
        template_key: templateKey,
        template,
        offer,
        scope,
        save_template: saveTemplate,
      };
      if (scope === 'one') {
        payload.customer_id = Number(oneCustomerId);
      } else {
        payload.customer_ids = Array.from(selected);
      }
      const res = await messagingAPI.blastSend(payload);
      const queued = res.data?.queued ?? selected.size;
      toast.success(`Sent ${queued} SMS${queued === 1 ? '' : 'es'}`);
      onOpenChange(false);
    } catch (err) {
      const data = err?.response?.data;
      const msg =
        data?.sms ||
        data?.recipients ||
        data?.customer_id ||
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
        description="Send any SMS template to all registered customers with a valid phone, or to one."
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquareText className="h-5 w-5" />
            Send SMS to customers
          </DialogTitle>
          <DialogDescription>
            Choose a message, send to everyone with a correct phone number, or pick one
            customer. Invalid or missing numbers are skipped. Debt collection only lists
            customers who currently owe.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Message</label>
              <div className="mt-1.5">
                <SearchableSelect
                  value={templateKey}
                  onChange={(e) => {
                    const next = e.target.value || '';
                    setTemplateKey(next);
                    const spec = (templates || []).find((t) => t.key === next);
                    setTemplate(spec?.body || '');
                  }}
                  options={templateOptions}
                  placeholder="Choose template"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Audience</label>
              <div className="mt-1.5 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={scope === 'all' ? 'default' : 'outline'}
                  onClick={() => setScope('all')}
                >
                  {templateKey === 'debt_reminder'
                    ? 'All debtors with valid phone'
                    : 'All with valid phone'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={scope === 'one' ? 'default' : 'outline'}
                  onClick={() => setScope('one')}
                >
                  One customer
                </Button>
              </div>
            </div>
          </div>

          {scope === 'one' ? (
            <div>
              <label className="text-sm font-medium">Customer</label>
              <div className="mt-1.5">
                <SearchableSelect
                  value={oneCustomerId}
                  onChange={(e) => setOneCustomerId(e.target.value || '')}
                  options={[{ id: '', name: 'Search customer…' }, ...customerOptions]}
                  placeholder="Search customer…"
                  onSearchTermChange={(term) => loadCustomerOptions(term)}
                />
              </div>
            </div>
          ) : null}

          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="blast-sms-template" className="text-sm font-medium">
                Message body
              </label>
              <p className="text-xs text-muted-foreground">
                {(selectedSpec?.placeholders || []).join(' · ') || 'Placeholders from template'}
              </p>
            </div>
            <textarea
              id="blast-sms-template"
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          {showOffer ? (
            <div>
              <label htmlFor="blast-sms-offer" className="text-sm font-medium">
                Offer line (fills {'{offer}'})
              </label>
              <Input
                id="blast-sms-offer"
                className="mt-1.5"
                value={offer}
                onChange={(e) => setOffer(e.target.value)}
                placeholder="e.g. Special prices on soap this week."
              />
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={saveTemplate}
                onChange={(e) => setSaveTemplate(e.target.checked)}
              />
              Save message as default for this template
            </label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleRefreshPreview}
              disabled={loading || !templateKey}
            >
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh preview
            </Button>
            {sample ? (
              <Badge variant="secondary">{smsPartsHint(sample.message_chars)}</Badge>
            ) : null}
          </div>

          {sample ? (
            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Sample to {sample.greeting_name}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{sample.message}</p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>
              <strong>{scope === 'one' ? recipients.length : selected.size}</strong>
              {scope === 'all' ? ` of ${recipients.length}` : ''} with valid phone
            </span>
            {preview?.skipped_no_phone > 0 ? (
              <span className="text-amber-700 dark:text-amber-400">
                {preview.skipped_no_phone} no phone
              </span>
            ) : null}
            {preview?.skipped_invalid_phone > 0 ? (
              <span className="text-amber-700 dark:text-amber-400">
                {preview.skipped_invalid_phone} invalid phone
              </span>
            ) : null}
          </div>

          {scope === 'all' ? (
            <div className="max-h-64 overflow-auto rounded-md border">
              <DataTable>
                <DataTableHeader>
                  <DataTableRow>
                    <DataTableHead className="w-10">
                      <input
                        type="checkbox"
                        aria-label="Select all customers"
                        checked={
                          recipients.length > 0 && selected.size === recipients.length
                        }
                        onChange={(e) => toggleAll(e.target.checked)}
                      />
                    </DataTableHead>
                    <DataTableHead>Customer</DataTableHead>
                    <DataTableHead>Phone</DataTableHead>
                  </DataTableRow>
                </DataTableHeader>
                <DataTableBody>
                  {loading && recipients.length === 0 ? (
                    <DataTableRow>
                      <DataTableCell colSpan={3}>Loading customers…</DataTableCell>
                    </DataTableRow>
                  ) : null}
                  {!loading && recipients.length === 0 ? (
                    <DataTableRow>
                      <DataTableCell colSpan={3}>
                        No registered customers with a valid phone number.
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
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSend}
            disabled={
              sending ||
              loading ||
              !templateKey ||
              (scope === 'one' ? !oneCustomerId || recipients.length === 0 : selected.size === 0)
            }
          >
            {sending
              ? 'Sending…'
              : scope === 'one'
                ? 'Send to this customer'
                : `Send to ${selected.size}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
