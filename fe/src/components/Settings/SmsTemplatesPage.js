import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquareText, RotateCcw, Save } from 'lucide-react';

import { messagingAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Label } from '../ui/label';

const CATEGORY_LABELS = {
  sales: 'Sales',
  debt: 'Debt & collections',
  payments: 'Payments',
};

function livePreview(body, sample) {
  if (!body || !sample) return '';
  let out = body;
  Object.entries(sample).forEach(([key, value]) => {
    out = out.split(`{${key}}`).join(String(value));
  });
  // sale templates may still mention debt_bit
  if (sample.balance_note != null) {
    out = out.split('{debt_bit}').join(String(sample.balance_note));
  }
  return out;
}

export default function SmsTemplatesPage() {
  const { permissions } = getStoredAuth();
  const canView =
    hasPermission(permissions, 'messaging', 'view') ||
    hasPermission(permissions, 'messaging', 'create') ||
    hasPermission(permissions, 'debt_management', 'view') ||
    hasPermission(permissions, 'debt_management', 'update');
  const canEdit =
    hasPermission(permissions, 'messaging', 'create') ||
    hasPermission(permissions, 'debt_management', 'update') ||
    hasPermission(permissions, 'settings', 'manage');

  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState('');
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await messagingAPI.listTemplates();
      const rows = res.data?.results || [];
      setTemplates(rows);
      setSelectedKey((prev) => {
        if (prev && rows.some((r) => r.key === prev)) return prev;
        return rows[0]?.key || '';
      });
    } catch {
      toast.error('Could not load SMS templates');
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canView) load();
    else setLoading(false);
  }, [canView, load]);

  const selected = useMemo(
    () => templates.find((t) => t.key === selectedKey) || null,
    [templates, selectedKey],
  );

  useEffect(() => {
    if (selected) setDraft(selected.body || '');
  }, [selected]);

  const samplePreview = useMemo(() => {
    if (!selected) return '';
    if (draft === selected.body) return selected.sample_preview || '';
    const demo = {
      first_name: 'Jane',
      sale_number: 'SALE-0001',
      total: '1500',
      paid: '1000',
      balance_note: ' Balance now KES 500.',
      debt_bit: ' Balance now KES 500.',
      amount: '200',
      balance: '300',
      name: 'Mama Mboga',
      store_name: 'Omuwenga Suppliers',
      customer_name: 'Jane',
      brand_blurb: 'Thank you for shopping with us.',
      invoice_no: 'INV-100',
      link: 'https://example.com/i/abc',
    };
    return livePreview(draft, demo);
  }, [selected, draft]);

  const dirty = selected && draft !== (selected.body || '');

  const handleSave = async () => {
    if (!selected || !canEdit) return;
    setSaving(true);
    try {
      const res = await messagingAPI.saveTemplate(selected.key, draft);
      const updated = res.data;
      setTemplates((prev) =>
        prev.map((t) => (t.key === updated.key ? { ...t, ...updated } : t)),
      );
      toast.success('Template saved');
    } catch (err) {
      const msg = err?.response?.data?.body || err?.response?.data?.detail || 'Save failed';
      toast.error(typeof msg === 'string' ? msg : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selected || !canEdit) return;
    setSaving(true);
    try {
      const res = await messagingAPI.resetTemplate(selected.key);
      const updated = res.data;
      setTemplates((prev) =>
        prev.map((t) => (t.key === updated.key ? { ...t, ...updated } : t)),
      );
      setDraft(updated.body || '');
      toast.success('Restored default template');
    } catch {
      toast.error('Could not restore default');
    } finally {
      setSaving(false);
    }
  };

  if (!canView) {
    return (
      <PageShell>
        <PageHeader title="SMS templates" description="Customer SMS wording for sales and debt." />
        <EmptyState
          icon={MessageSquareText}
          title="No access"
          description="You need messaging or debt management permission to view SMS templates."
        />
      </PageShell>
    );
  }

  if (loading) return <PageLoading rows={5} />;

  const byCategory = templates.reduce((acc, t) => {
    const cat = t.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  return (
    <PageShell>
      <PageHeader
        title="SMS templates"
        description="Edit the default messages customers receive for sales, debt, and invoices. Changes apply to the next send."
      >
        <Button type="button" variant="outline" asChild>
          <Link to="/customers/debt">Debt reminders</Link>
        </Button>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <nav className="space-y-4 rounded-lg border bg-card p-3">
          {Object.entries(byCategory).map(([cat, rows]) => (
            <div key={cat}>
              <p className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {CATEGORY_LABELS[cat] || cat}
              </p>
              <ul className="space-y-0.5">
                {rows.map((t) => (
                  <li key={t.key}>
                    <button
                      type="button"
                      onClick={() => setSelectedKey(t.key)}
                      className={`flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm transition-colors ${
                        selectedKey === t.key
                          ? 'bg-primary/10 font-medium text-foreground'
                          : 'hover:bg-muted/60'
                      }`}
                    >
                      <span>{t.label}</span>
                      {t.is_customized ? (
                        <Badge variant="secondary" className="ml-2 text-[10px]">
                          Edited
                        </Badge>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {selected ? (
          <section className="space-y-4 rounded-lg border bg-card p-4 shadow-sm">
            <div>
              <h2 className="text-base font-semibold">{selected.label}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{selected.description}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Placeholders:{' '}
                {(selected.placeholders || []).map((p) => (
                  <code key={p} className="mr-1 rounded bg-muted px-1 py-0.5">
                    {p}
                  </code>
                ))}
              </p>
            </div>

            <div>
              <Label htmlFor="sms-template-body">Message</Label>
              <textarea
                id="sms-template-body"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={!canEdit}
                rows={5}
                className="mt-1.5 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                {draft.length} characters · aim for under 160 for one SMS part
              </p>
            </div>

            <div className="rounded-md border bg-muted/30 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Preview
              </p>
              <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">{samplePreview}</p>
            </div>

            {canEdit ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={handleSave} disabled={saving || !dirty}>
                  <Save className="mr-1.5 h-4 w-4" />
                  {saving ? 'Saving…' : 'Save'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleReset}
                  disabled={saving || !selected.is_customized}
                >
                  <RotateCcw className="mr-1.5 h-4 w-4" />
                  Restore default
                </Button>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">You can view templates but not edit them.</p>
            )}
          </section>
        ) : (
          <EmptyState
            icon={MessageSquareText}
            title="No templates"
            description="SMS templates will appear here once the messaging module is configured."
          />
        )}
      </div>
    </PageShell>
  );
}
