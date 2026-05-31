import React, { useEffect, useState } from 'react';
import { Image, Receipt, CreditCard, Package, Info } from 'lucide-react';

import { PageShell, PageHeader } from '../page';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { storeSettingsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { PAYMENT_METHODS } from '../../utils/paymentMethods';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ModuleSettingsCard from './ModuleSettingsCard';
import { MODULE_SETTINGS_CARDS } from './moduleSettingsCards';

export default function SystemSettings() {
  const { settings, applyLocal } = useStoreSettings();
  const [form, setForm] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm({ ...settings });
  }, [settings]);

  const togglePayment = (id) => {
    setForm((prev) => {
      const current = prev.enabled_payment_methods || [];
      const next = current.includes(id)
        ? current.filter((m) => m !== id)
        : [...current, id];
      return { ...prev, enabled_payment_methods: next.length ? next : [id] };
    });
  };

  const handleSave = async () => {
    if (!form) return;
    if (!(form.enabled_payment_methods || []).length) {
      toast.warning('Select at least one payment method.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        allow_sales_add_products: form.allow_sales_add_products,
        sales_catalog_skip_pricing: form.sales_catalog_skip_pricing,
        hide_entity_status_toggles: form.hide_entity_status_toggles,
        receipt_header_text: form.receipt_header_text || '',
        receipt_footer_text: form.receipt_footer_text || '',
        receipt_show_logo: form.receipt_show_logo,
        receipt_show_sku: form.receipt_show_sku,
        receipt_auto_print: form.receipt_auto_print,
        enabled_payment_methods: form.enabled_payment_methods || [],
      };

      let res;
      if (logoFile) {
        const body = new FormData();
        Object.entries(payload).forEach(([key, value]) => {
          if (key === 'enabled_payment_methods') {
            body.append(key, JSON.stringify(value));
          } else if (typeof value === 'boolean') {
            body.append(key, value ? 'true' : 'false');
          } else {
            body.append(key, value);
          }
        });
        body.append('receipt_logo', logoFile);
        res = await storeSettingsAPI.update(body);
      } else {
        res = await storeSettingsAPI.update(payload);
      }
      applyLocal(res.data);
      setLogoFile(null);
      window.dispatchEvent(new CustomEvent('storeSettingsUpdated', { detail: res.data }));
      toast.success('System settings saved');
    } catch (err) {
      const detail = err.response?.data;
      const msg =
        (typeof detail === 'object' &&
          Object.values(detail).flat().join(', ')) ||
        detail?.detail ||
        err.message ||
        'Could not save settings';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const clearLogo = async () => {
    setSaving(true);
    try {
      const res = await storeSettingsAPI.update({ clear_receipt_logo: true });
      applyLocal(res.data);
      setForm((prev) => ({ ...prev, receipt_logo_url: null }));
      toast.success('Receipt logo removed');
    } catch (err) {
      toast.error('Could not remove logo');
    } finally {
      setSaving(false);
    }
  };

  if (!form) {
    return (
      <PageShell narrow>
        <PageHeader title="System Settings" description="Loading…" />
      </PageShell>
    );
  }

  return (
    <PageShell narrow>
      <PageHeader
        title="System Settings"
        description="Store-wide POS rules, receipt branding, and per-module feature toggles."
      />

      <div className="space-y-3">
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="h-4 w-4 text-primary" />
              How settings are organised
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">Store rules</span> (top section, receipt,
              payments) apply to the whole business. Click <span className="font-medium text-foreground">Save settings</span>{' '}
              to persist them.
            </p>
            <p>
              <span className="font-medium text-foreground">Module toggles</span> below save immediately
              when you check or uncheck them. They gate UI and API behaviour without deleting data.
            </p>
            <p>
              <span className="font-medium text-foreground">Module Settings</span> (separate page) controls
              which modules and install-level features are enabled. Both layers must allow something before
              it appears in the app.
            </p>
            <p>
              After upgrading, run{' '}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">python manage.py init_module_settings</code>{' '}
              once so new toggles exist in the database.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Package className="h-4 w-4 text-primary" />
              Store POS rules
            </CardTitle>
            <CardDescription>
              Cross-cutting checkout and catalog behaviour. Saved with the button at the bottom of this page.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={form.allow_sales_add_products}
                onChange={(e) =>
                  setForm({ ...form, allow_sales_add_products: e.target.checked })
                }
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Allow sales to add products</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Shows Products and Categories in the sales navigation when the products module is on.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={form.sales_catalog_skip_pricing}
                onChange={(e) =>
                  setForm({ ...form, sales_catalog_skip_pricing: e.target.checked })
                }
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Sales skip pricing fields</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Managers and super admins still set MRP, cost, and selling price.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={form.hide_entity_status_toggles}
                onChange={(e) =>
                  setForm({ ...form, hide_entity_status_toggles: e.target.checked })
                }
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Hide all active / inactive controls</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Store-wide override: hides status badges, filters, and toggles for products,
                  customers, employees, suppliers, users, and categories — even when a module&apos;s
                  status toggle is on.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>

        {MODULE_SETTINGS_CARDS.map((card) => (
          <ModuleSettingsCard key={card.module} {...card} />
        ))}

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <CreditCard className="h-4 w-4 text-primary" />
              Payment methods
            </CardTitle>
            <CardDescription>Only selected methods appear at POS checkout.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {PAYMENT_METHODS.map((m) => {
                const on = (form.enabled_payment_methods || []).includes(m.id);
                const Icon = m.icon;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => togglePayment(m.id)}
                    className={`flex flex-col items-center gap-1 rounded-md border px-2 py-2.5 text-xs font-medium transition-colors ${
                      on
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-accent'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    {m.label}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Receipt className="h-4 w-4 text-primary" />
              Receipt
            </CardTitle>
            <CardDescription>Logo and messages printed on thermal receipts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Image className="h-4 w-4" />
                Logo
              </Label>
              {form.receipt_logo_url && (
                <img
                  src={form.receipt_logo_url}
                  alt="Receipt logo"
                  className="h-16 w-auto rounded border object-contain"
                />
              )}
              <Input
                type="file"
                accept="image/*"
                onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
              />
              {form.receipt_logo_url && (
                <Button type="button" variant="outline" size="sm" onClick={clearLogo} disabled={saving}>
                  Remove logo
                </Button>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.receipt_show_logo}
                onChange={(e) => setForm({ ...form, receipt_show_logo: e.target.checked })}
              />
              Show logo on receipt
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.receipt_show_sku}
                onChange={(e) => setForm({ ...form, receipt_show_sku: e.target.checked })}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Show SKU on receipt</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Off by default — line items show product name only.
                </span>
              </span>
            </label>
            <div className="space-y-1">
              <Label htmlFor="receipt_header">Header message</Label>
              <Input
                id="receipt_header"
                value={form.receipt_header_text || ''}
                onChange={(e) => setForm({ ...form, receipt_header_text: e.target.value })}
                placeholder="e.g. Welcome to our store"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="receipt_footer">Footer message</Label>
              <Input
                id="receipt_footer"
                value={form.receipt_footer_text || ''}
                onChange={(e) => setForm({ ...form, receipt_footer_text: e.target.value })}
                placeholder="Thank you for your business!"
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.receipt_auto_print}
                onChange={(e) => setForm({ ...form, receipt_auto_print: e.target.checked })}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Auto-print after sale</span>
                <span className="mt-0.5 block text-muted-foreground">
                  Off by default — cashier taps Print after reviewing the receipt.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>

        <div className="flex flex-col items-end gap-1">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save store settings'}
          </Button>
          <p className="text-xs text-muted-foreground">
            Module toggles above save automatically when changed.
          </p>
        </div>
      </div>
    </PageShell>
  );
}
