import React, { useEffect, useState } from 'react';
import { Image, Receipt, CreditCard, Package, ClipboardCheck, SlidersHorizontal } from 'lucide-react';

import { PageShell, PageHeader } from '../page';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { storeSettingsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { PAYMENT_METHODS } from '../../utils/paymentMethods';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
  storeSettingsEditNeedsReason,
} from '../../utils/makerChecker';
import ModuleSettingsCard from './ModuleSettingsCard';
import { MODULE_SETTINGS_CARDS } from './moduleSettingsCards';
import SettingToggleRow from './SettingToggleRow';

function StoreCheckboxRow({ id, checked, onChange, disabled, label, description }) {
  return (
    <SettingToggleRow
      settingKey={id}
      item={{ label, description }}
      checked={checked}
      disabled={disabled}
      onRequestChange={(_, next) => onChange(next)}
      testId={id}
    />
  );
}

export default function SystemSettings() {
  const { settings, applyLocal } = useStoreSettings();
  const [form, setForm] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [changeReason, setChangeReason] = useState('');
  const [openModule, setOpenModule] = useState('products');
  const makerCheckerOn = isMakerCheckerEnabled(settings);

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
    const needsReason = makerCheckerOn && storeSettingsEditNeedsReason(form, settings);
    if (needsReason && !changeReason.trim()) {
      toast.warning('Enter a reason for these store setting changes.');
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
        maker_checker_enabled: form.maker_checker_enabled,
        maker_checker_sales_controls: form.maker_checker_sales_controls,
        emergency_stock_mode: form.emergency_stock_mode,
      };
      if (needsReason) {
        payload.reason = changeReason.trim();
      }

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
      const data = res.data?.settings || res.data;
      applyLocal(data);
      setLogoFile(null);
      setChangeReason('');
      window.dispatchEvent(new CustomEvent('storeSettingsUpdated', { detail: data }));
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(pendingApprovalToastMessage());
      } else {
        toast.success('System settings saved');
      }
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
        description="Store rules save together on the Store & receipt tab. Module features save when you confirm each change."
      />

      <Tabs defaultValue="store" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="store">Store & receipt</TabsTrigger>
          <TabsTrigger value="modules" data-testid="system-settings-tab-modules">
            Module features
          </TabsTrigger>
        </TabsList>

        <TabsContent value="store" className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <ClipboardCheck className="h-4 w-4 text-primary" />
                Maker-checker
              </CardTitle>
              <CardDescription>
                Sensitive price, stock, delete, and sale void/refund changes can require approval
                before they affect POS, inventory, and reports.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <StoreCheckboxRow
                id="maker_checker_enabled"
                checked={!!form.maker_checker_enabled}
                onChange={(v) => setForm({ ...form, maker_checker_enabled: v })}
                label="Enable maker-checker"
                description='Proposals show as "pending approval" until a checker approves them in Reports → Pending approvals.'
              />
              <StoreCheckboxRow
                id="emergency_stock_mode"
                checked={!!form.emergency_stock_mode}
                disabled={!form.maker_checker_enabled}
                onChange={(v) => setForm({ ...form, emergency_stock_mode: v })}
                label="Emergency stock mode"
                description="Positive stock adjustments apply immediately (still logged). Use only for zero-stock emergencies."
              />
              <StoreCheckboxRow
                id="maker_checker_sales_controls"
                checked={!!form.maker_checker_sales_controls}
                disabled={!form.maker_checker_enabled}
                onChange={(v) => setForm({ ...form, maker_checker_sales_controls: v })}
                label="Optional: post-completion sale edits"
                description="Future feature — approval for notes/payment method only. Off by default; voids/refunds use the main maker-checker toggle above."
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Package className="h-4 w-4 text-primary" />
                Store POS rules
              </CardTitle>
              <CardDescription>Cross-cutting checkout and catalog behaviour.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <StoreCheckboxRow
                id="allow_sales_add_products"
                checked={form.allow_sales_add_products}
                onChange={(v) => setForm({ ...form, allow_sales_add_products: v })}
                label="Allow sales to add products"
                description="Shows Products and Categories in the sales navigation when the products module is on."
              />
              <StoreCheckboxRow
                id="sales_catalog_skip_pricing"
                checked={form.sales_catalog_skip_pricing}
                onChange={(v) => setForm({ ...form, sales_catalog_skip_pricing: v })}
                label="Sales skip pricing fields"
                description="Managers and super admins still set MRP, cost, and selling price."
              />
              <StoreCheckboxRow
                id="hide_entity_status_toggles"
                checked={form.hide_entity_status_toggles}
                onChange={(v) => setForm({ ...form, hide_entity_status_toggles: v })}
                label="Hide all active / inactive controls"
                description="Store-wide override: hides status badges, filters, and toggles across catalog entities."
              />
            </CardContent>
          </Card>

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
              <StoreCheckboxRow
                id="receipt_show_logo"
                checked={form.receipt_show_logo}
                onChange={(v) => setForm({ ...form, receipt_show_logo: v })}
                label="Show logo on receipt"
              />
              <StoreCheckboxRow
                id="receipt_show_sku"
                checked={form.receipt_show_sku}
                onChange={(v) => setForm({ ...form, receipt_show_sku: v })}
                label="Show SKU on receipt"
                description="Off by default — line items show product name only."
              />
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
              <StoreCheckboxRow
                id="receipt_auto_print"
                checked={form.receipt_auto_print}
                onChange={(v) => setForm({ ...form, receipt_auto_print: v })}
                label="Auto-print after sale"
                description="Off by default — cashier taps Print after reviewing the receipt."
              />
            </CardContent>
          </Card>

          {makerCheckerOn && storeSettingsEditNeedsReason(form, settings) ? (
            <ChangeReasonField context="settings" value={changeReason} onChange={setChangeReason} />
          ) : null}

          <div className="sticky bottom-2 z-10 flex justify-end rounded-lg border bg-background/95 p-3 shadow-sm backdrop-blur">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save store settings'}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="modules" className="space-y-3">
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <SlidersHorizontal className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Expand a module to review toggles. Sensitive rules ask for confirmation; with maker-checker
            on, changes may need manager approval.
          </p>
          {MODULE_SETTINGS_CARDS.map((card) => (
            <ModuleSettingsCard
              key={card.module}
              {...card}
              expanded={openModule === card.module}
              onToggleExpand={() =>
                setOpenModule((prev) => (prev === card.module ? null : card.module))
              }
            />
          ))}
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}
