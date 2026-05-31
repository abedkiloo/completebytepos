import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Plus,
  Search,
  Users as UsersIcon,
  Mail,
  Phone,
  MapPin,
  Loader2,
  Pencil,
  Trash2,
  X,
} from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { ScrollArea } from '../ui/scroll-area';
import { cn } from '../../lib/cn';
import { PageShell, PageHeader } from '../page';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  customersShowCustomerCode,
  customersShowOutstandingBalance,
  customersEnableCreate,
  customersEnableEdit,
  customersEnableDelete,
  customersShowCustomerType,
  customersShowTaxId,
  customersShowNotes,
  customersShowStatus,
} from '../../utils/customerDisplay';

const EMPTY_FORM = {
  name: '',
  customer_type: 'individual',
  email: '',
  phone: '',
  address: '',
  city: '',
  country: 'Kenya',
  tax_id: '',
  notes: '',
  is_active: true,
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const Customers = () => {
  const { settings: customerModuleSettings } = useModuleSettings('customers');
  const { settings: storeSettings } = useStoreSettings();

  const showCustomerCode = customersShowCustomerCode(customerModuleSettings);
  const showOutstanding = customersShowOutstandingBalance(customerModuleSettings);
  const canCreate = customersEnableCreate(customerModuleSettings);
  const canEdit = customersEnableEdit(customerModuleSettings);
  const canDelete = customersEnableDelete(customerModuleSettings);
  const showCustomerType = customersShowCustomerType(customerModuleSettings);
  const showTaxId = customersShowTaxId(customerModuleSettings);
  const showNotes = customersShowNotes(customerModuleSettings);
  const showStatus = customersShowStatus(customerModuleSettings, storeSettings);

  // --- Data ---
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // --- Editor / delete confirm state ---
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // --- Data loading (debounced search) ---
  const loadCustomers = useCallback(async (signal) => {
    setLoading(true);
    try {
      const params = { is_active: 'true' };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      const response = await customersAPI.list(params);
      if (signal?.aborted) return;
      const data = response.data.results || response.data || [];
      setCustomers(Array.isArray(data) ? data : []);
    } catch (error) {
      if (signal?.aborted) return;
      console.error('Error loading customers:', error);
      toast.error('Failed to load customers');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    const controller = new AbortController();
    const t = setTimeout(() => loadCustomers(controller.signal), 200);
    return () => {
      controller.abort();
      clearTimeout(t);
    };
  }, [loadCustomers]);

  // --- Derived ---
  const totals = useMemo(
    () => ({
      count: customers.length,
      withDebt: showOutstanding
        ? customers.filter((c) => (c.total_outstanding || 0) > 0).length
        : 0,
      totalOwed: showOutstanding
        ? customers.reduce((sum, c) => sum + parseFloat(c.total_outstanding || 0), 0)
        : 0,
    }),
    [customers, showOutstanding]
  );

  // --- Editor handlers ---
  const openCreate = () => {
    setEditingCustomer(null);
    setFormData(EMPTY_FORM);
    setFormErrors({});
    setShowModal(true);
  };

  const openEdit = (customer) => {
    setEditingCustomer(customer);
    setFormData({
      name: customer.name || '',
      customer_type: customer.customer_type || 'individual',
      email: customer.email || '',
      phone: customer.phone || '',
      address: customer.address || '',
      city: customer.city || '',
      country: customer.country || 'Kenya',
      tax_id: customer.tax_id || '',
      notes: customer.notes || '',
      is_active: customer.is_active !== undefined ? customer.is_active : true,
    });
    setFormErrors({});
    setShowModal(true);
  };

  const closeModal = () => {
    if (saving) return;
    setShowModal(false);
    setEditingCustomer(null);
    setFormErrors({});
  };

  const updateField = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (formErrors[key]) {
      setFormErrors((prev) => ({ ...prev, [key]: '' }));
    }
  };

  const validate = () => {
    const errors = {};
    const name = formData.name?.trim() || '';
    if (!name) errors.name = 'Customer name is required';
    else if (name.length < 2) errors.name = 'Name must be at least 2 characters';

    const email = formData.email?.trim() || '';
    if (email && !EMAIL_RE.test(email)) {
      errors.email = 'Please enter a valid email address';
    }
    return errors;
  };

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    const errors = validate();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error(Object.values(errors)[0]);
      return;
    }

    const payload = {
      name: formData.name.trim(),
      customer_type: formData.customer_type,
      email: formData.email.trim(),
      phone: formData.phone.trim(),
      address: formData.address.trim(),
      city: formData.city.trim(),
      country: formData.country.trim() || 'Kenya',
      tax_id: formData.tax_id.trim(),
      notes: formData.notes.trim(),
      is_active: formData.is_active,
    };

    setSaving(true);
    try {
      if (editingCustomer) {
        await customersAPI.update(editingCustomer.id, payload);
        toast.success('Customer updated');
      } else {
        await customersAPI.create(payload);
        toast.success('Customer created');
      }
      setShowModal(false);
      setEditingCustomer(null);
      loadCustomers();
    } catch (error) {
      // Field-level DRF errors → inline; otherwise toast.
      const data = error.response?.data;
      if (data && typeof data === 'object' && !data.error && !data.detail) {
        const backendErrors = {};
        for (const [field, messages] of Object.entries(data)) {
          backendErrors[field] = Array.isArray(messages)
            ? messages.join(', ')
            : String(messages);
        }
        setFormErrors(backendErrors);
        toast.error(Object.values(backendErrors)[0] || 'Failed to save customer');
      } else {
        const msg =
          data?.error || data?.detail || error.message || 'Failed to save customer';
        toast.error(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await customersAPI.delete(pendingDelete.id);
      toast.success('Customer deleted');
      setPendingDelete(null);
      loadCustomers();
    } catch (error) {
      toast.error(
        'Failed to delete customer: ' +
          (error.response?.data?.error || error.message)
      );
    } finally {
      setDeleting(false);
    }
  };

  return (
    <PageShell>
        <PageHeader
          title="Customers"
          description="Manage shoppers, their contact details, and outstanding balances."
        >
          {canCreate && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              Add customer
            </Button>
          )}
        </PageHeader>

        {/* --- Summary chips --- */}
        <div
          className={cn(
            'grid grid-cols-1 gap-3',
            showOutstanding ? 'sm:grid-cols-3' : 'sm:grid-cols-1'
          )}
        >
          <SummaryCard
            icon={UsersIcon}
            label="Total customers"
            value={totals.count.toLocaleString()}
          />
          {showOutstanding && (
            <>
              <SummaryCard
                icon={UsersIcon}
                label="With balance owing"
                value={totals.withDebt.toLocaleString()}
                tone={totals.withDebt > 0 ? 'warning' : 'default'}
              />
              <SummaryCard
                icon={UsersIcon}
                label="Total outstanding"
                value={formatCurrency(totals.totalOwed)}
                tone={totals.totalOwed > 0 ? 'destructive' : 'default'}
              />
            </>
          )}
        </div>

        {/* --- Search toolbar --- */}
        <div className="relative max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name, phone, email or code…"
            className="h-10 pl-9"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* --- Table --- */}
        <div className="overflow-hidden rounded-lg border bg-background">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Customer</th>
                  <th className="px-4 py-2.5 text-left font-medium">Contact</th>
                  <th className="px-4 py-2.5 text-left font-medium">City</th>
                  {showOutstanding && (
                    <th className="px-4 py-2.5 text-right font-medium">Outstanding</th>
                  )}
                  {showStatus && (
                    <th className="px-4 py-2.5 text-left font-medium">Status</th>
                  )}
                  {(canEdit || canDelete) && (
                    <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading && customers.length === 0 ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({
                        length:
                          4 + (showOutstanding ? 1 : 0) + (showStatus ? 1 : 0) + (canEdit || canDelete ? 1 : 0),
                      }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : customers.length === 0 ? (
                  <tr>
                    <td
                      colSpan={
                        4 +
                        (showOutstanding ? 1 : 0) +
                        (showStatus ? 1 : 0) +
                        (canEdit || canDelete ? 1 : 0)
                      }
                      className="px-4 py-12 text-center"
                    >
                      <EmptyState
                        onCreate={canCreate ? openCreate : undefined}
                        searchQuery={searchQuery}
                      />
                    </td>
                  </tr>
                ) : (
                  customers.map((customer) => (
                    <CustomerRow
                      key={customer.id}
                      customer={customer}
                      showCustomerCode={showCustomerCode}
                      showOutstanding={showOutstanding}
                      showStatus={showStatus}
                      showCustomerType={showCustomerType}
                      canEdit={canEdit}
                      canDelete={canDelete}
                      onEdit={() => openEdit(customer)}
                      onDelete={() => setPendingDelete(customer)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      {/* --- Editor dialog --- */}
      <CustomerFormDialog
        open={showModal}
        onOpenChange={(next) => (next ? setShowModal(true) : closeModal())}
        editing={editingCustomer}
        formData={formData}
        formErrors={formErrors}
        onChange={updateField}
        onSubmit={handleSubmit}
        saving={saving}
        showCustomerType={showCustomerType}
        showTaxId={showTaxId}
        showNotes={showNotes}
        showStatus={showStatus}
      />

      {/* --- Delete confirm --- */}
      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="Delete customer"
        message={
          pendingDelete
            ? `Delete ${pendingDelete.name}? Their sales history will be preserved but they will no longer appear in customer pickers.`
            : ''
        }
        confirmText="Delete customer"
        cancelText="Keep"
        type="danger"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => (deleting ? null : setPendingDelete(null))}
      />
      </PageShell>
  );
};

function SummaryCard({ icon: Icon, label, value, tone = 'default' }) {
  const toneClasses = {
    default: 'text-foreground',
    warning: 'text-warning',
    destructive: 'text-destructive',
  };
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-muted">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="min-w-0">
        <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div className={cn('text-lg font-semibold tabular-nums', toneClasses[tone])}>
          {value}
        </div>
      </div>
    </div>
  );
}

function CustomerRow({
  customer,
  showCustomerCode,
  showOutstanding,
  showStatus,
  showCustomerType,
  canEdit,
  canDelete,
  onEdit,
  onDelete,
}) {
  const outstanding = parseFloat(customer.total_outstanding || 0);
  return (
    <tr
      className={cn(
        'transition-colors hover:bg-muted/40',
        showStatus && !customer.is_active && 'opacity-60'
      )}
    >
      <td className="px-4 py-3">
        <div className="flex flex-col">
          <span className="font-medium text-foreground">{customer.name}</span>
          {showCustomerCode && customer.customer_code && (
            <span className="font-mono text-xs text-muted-foreground">
              {customer.customer_code}
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-0.5 text-xs">
          {customer.email && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Mail className="h-3 w-3" />
              <span className="truncate">{customer.email}</span>
            </span>
          )}
          {customer.phone && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Phone className="h-3 w-3" />
              <span>{customer.phone}</span>
            </span>
          )}
          {!customer.email && !customer.phone && (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-muted-foreground">
        {customer.city ? (
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3 w-3 text-muted-foreground" />
            {customer.city}
          </span>
        ) : (
          '—'
        )}
      </td>
      {showOutstanding && (
        <td className="px-4 py-3 text-right">
          <span
            className={cn(
              'font-semibold tabular-nums',
              outstanding > 0 ? 'text-destructive' : 'text-muted-foreground'
            )}
          >
            {formatCurrency(outstanding)}
          </span>
        </td>
      )}
      {showStatus && (
        <td className="px-4 py-3">
          <Badge variant={customer.is_active ? 'success' : 'outline'}>
            {customer.is_active ? 'Active' : 'Inactive'}
          </Badge>
          {showCustomerType && customer.customer_type === 'business' && (
            <Badge variant="secondary" className="ml-1.5">
              Business
            </Badge>
          )}
        </td>
      )}
      {(canEdit || canDelete) && (
        <td className="px-4 py-3">
          <div className="flex items-center justify-end gap-1">
            {canEdit && (
              <Button variant="ghost" size="sm" onClick={onEdit} aria-label="Edit customer">
                <Pencil className="h-3.5 w-3.5" />
                <span className="sr-only sm:not-sr-only sm:ml-1">Edit</span>
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                aria-label="Delete customer"
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span className="sr-only sm:not-sr-only sm:ml-1">Delete</span>
              </Button>
            )}
          </div>
        </td>
      )}
    </tr>
  );
}

function EmptyState({ onCreate, searchQuery }) {
  if (searchQuery) {
    return (
      <div className="flex flex-col items-center gap-2 text-muted-foreground">
        <UsersIcon className="h-8 w-8 opacity-50" />
        <p className="font-medium text-foreground">No customers match “{searchQuery}”</p>
        <p className="text-sm">Try a different name, phone, or email.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-3 text-muted-foreground">
      <UsersIcon className="h-10 w-10 opacity-40" />
      <div>
        <p className="font-medium text-foreground">No customers yet</p>
        <p className="text-sm">
          Add a customer to start tracking purchases, balances and wallet credit.
        </p>
      </div>
      {onCreate && (
        <Button onClick={onCreate} variant="default" size="sm">
          <Plus className="h-4 w-4" />
          Add your first customer
        </Button>
      )}
    </div>
  );
}

function CustomerFormDialog({
  open,
  onOpenChange,
  editing,
  formData,
  formErrors,
  onChange,
  onSubmit,
  saving,
  showCustomerType = true,
  showTaxId = true,
  showNotes = true,
  showStatus = true,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-2xl"
        description={
          editing
            ? 'Update this customer\u2019s contact details, credit limit, and notes.'
            : 'Create a new customer profile to track sales, wallet balance, and credit.'
        }
      >
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit customer' : 'Add customer'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <ScrollArea className="max-h-[60vh] pr-3">
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Name" htmlFor="cust-name" required error={formErrors.name}>
                  <Input
                    id="cust-name"
                    value={formData.name}
                    onChange={(e) => onChange('name', e.target.value)}
                    placeholder="Jane Doe"
                    autoFocus
                  />
                </Field>
                {showCustomerType && (
                <Field label="Type" htmlFor="cust-type">
                  <SegmentedControl
                    value={formData.customer_type}
                    onChange={(v) => onChange('customer_type', v)}
                    options={[
                      { value: 'individual', label: 'Individual' },
                      { value: 'business', label: 'Business' },
                    ]}
                  />
                </Field>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Email" htmlFor="cust-email" error={formErrors.email}>
                  <Input
                    id="cust-email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => onChange('email', e.target.value)}
                    placeholder="jane@example.com"
                  />
                </Field>
                <Field label="Phone" htmlFor="cust-phone" error={formErrors.phone}>
                  <Input
                    id="cust-phone"
                    type="tel"
                    inputMode="tel"
                    value={formData.phone}
                    onChange={(e) => onChange('phone', e.target.value)}
                    placeholder="+254…"
                  />
                </Field>
              </div>

              <Field label="Address" htmlFor="cust-address">
                <textarea
                  id="cust-address"
                  value={formData.address}
                  onChange={(e) => onChange('address', e.target.value)}
                  rows={2}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="Street, building, area…"
                />
              </Field>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="City" htmlFor="cust-city">
                  <Input
                    id="cust-city"
                    value={formData.city}
                    onChange={(e) => onChange('city', e.target.value)}
                  />
                </Field>
                <Field label="Country" htmlFor="cust-country">
                  <Input
                    id="cust-country"
                    value={formData.country}
                    onChange={(e) => onChange('country', e.target.value)}
                  />
                </Field>
              </div>

              {showTaxId && (
              <Field
                label="Tax ID / VAT number"
                htmlFor="cust-tax"
                hint="Leave blank if not applicable."
              >
                <Input
                  id="cust-tax"
                  value={formData.tax_id}
                  onChange={(e) => onChange('tax_id', e.target.value)}
                />
              </Field>
              )}

              {showNotes && (
              <Field label="Notes" htmlFor="cust-notes">
                <textarea
                  id="cust-notes"
                  value={formData.notes}
                  onChange={(e) => onChange('notes', e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="Internal notes (preferences, delivery instructions…)"
                />
              </Field>
              )}

              {showStatus && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => onChange('is_active', e.target.checked)}
                  className="h-4 w-4 rounded border-input text-primary focus:ring-1 focus:ring-ring"
                />
                <span>Active — appears in customer pickers</span>
              </label>
              )}
            </div>
          </ScrollArea>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : editing ? (
                'Save changes'
              ) : (
                'Create customer'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, htmlFor, required = false, error, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="flex items-center gap-1">
        <span>{label}</span>
        {required && <span className="text-destructive">*</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function SegmentedControl({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-md border bg-background">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'h-10 px-4 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md',
            value === opt.value
              ? 'bg-primary text-primary-foreground'
              : 'text-foreground hover:bg-accent'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export default Customers;
