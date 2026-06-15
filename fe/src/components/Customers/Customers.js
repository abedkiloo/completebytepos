import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
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
  Wallet,
} from 'lucide-react';

import { customersAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
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
import { cn } from '../../lib/cn';
import { PageShell, PageHeader, ListPaginationRail } from '../page';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  customersShowCustomerCode,
  customersShowOutstandingBalance,
  customersShowWalletBalance,
  customersEnableWalletPayment,
  customersEnableCreate,
  customersEnableEdit,
  customersEnableDelete,
  customersShowCustomerType,
  customersShowTaxId,
  customersShowNotes,
  customersShowStatus,
} from '../../utils/customerDisplay';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
import { CustomerWalletBalance } from './CustomerWalletBalance';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';

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
  const showWallet = customersShowWalletBalance(customerModuleSettings);
  const canRecordWalletPayment = customersEnableWalletPayment(customerModuleSettings);
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
  const debouncedSearch = useDebouncedValue(searchQuery);

  // --- Editor / delete confirm state ---
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [walletPaymentCustomer, setWalletPaymentCustomer] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });

  // --- Data loading (debounced search) ---
  const loadCustomers = useCallback(async (signal) => {
    setLoading(true);
    try {
      const params = {
        is_active: 'true',
        page: pagination.page,
        page_size: pagination.page_size,
      };
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      const response = await customersAPI.list(params);
      if (signal?.aborted) return;
      const data = response.data.results || response.data || [];
      setCustomers(Array.isArray(data) ? data : []);
      setPagination((prev) => ({
        ...prev,
        count: response.data?.count ?? (Array.isArray(data) ? data.length : 0),
      }));
    } catch (error) {
      if (signal?.aborted) return;
      console.error('Error loading customers:', error);
      toast.error('Failed to load customers');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [debouncedSearch, pagination.page, pagination.page_size]);

  useEffect(() => {
    setPagination((prev) => (prev.page === 1 ? prev : { ...prev, page: 1 }));
  }, [debouncedSearch]);

  useEffect(() => {
    const controller = new AbortController();
    loadCustomers(controller.signal);
    return () => controller.abort();
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
      withWalletDebt: showWallet
        ? customers.filter((c) => getWalletDebtAmount(c.wallet_balance) > 0).length
        : 0,
      totalWalletDebt: showWallet
        ? customers.reduce((sum, c) => sum + getWalletDebtAmount(c.wallet_balance), 0)
        : 0,
    }),
    [customers, showOutstanding, showWallet]
  );

  const tableColumnCount =
    4 +
    (showOutstanding ? 1 : 0) +
    (showWallet ? 1 : 0) +
    (showStatus ? 1 : 0) +
    (canEdit || canDelete || canRecordWalletPayment ? 1 : 0);

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
          description="Manage shoppers, contact details, invoice balances, and POS wallet debt."
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
            showOutstanding && showWallet
              ? 'sm:grid-cols-2 lg:grid-cols-5'
              : showOutstanding || showWallet
                ? 'sm:grid-cols-3'
                : 'sm:grid-cols-1'
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
                label="With invoice balance"
                value={totals.withDebt.toLocaleString()}
                tone={totals.withDebt > 0 ? 'warning' : 'default'}
              />
              <SummaryCard
                icon={UsersIcon}
                label="Invoice outstanding"
                value={formatCurrency(totals.totalOwed)}
                tone={totals.totalOwed > 0 ? 'destructive' : 'default'}
              />
            </>
          )}
          {showWallet && (
            <>
              <SummaryCard
                icon={Wallet}
                label="With wallet debt"
                value={totals.withWalletDebt.toLocaleString()}
                tone={totals.withWalletDebt > 0 ? 'warning' : 'default'}
              />
              <SummaryCard
                icon={Wallet}
                label="Total wallet debt"
                value={formatCurrency(totals.totalWalletDebt)}
                tone={totals.totalWalletDebt > 0 ? 'destructive' : 'default'}
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
        <ListPaginationRail
          page={pagination.page}
          pageSize={pagination.page_size}
          totalCount={pagination.count}
          suffix={`${pagination.count} customers`}
          onPageChange={(nextPage) =>
            setPagination((prev) => ({ ...prev, page: nextPage }))
          }
        >
        <div className="overflow-hidden rounded-lg border bg-background">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Customer</th>
                  <th className="px-4 py-2.5 text-left font-medium">Contact</th>
                  <th className="px-4 py-2.5 text-left font-medium">City</th>
                  {showOutstanding && (
                    <th className="px-4 py-2.5 text-right font-medium">Invoice balance</th>
                  )}
                  {showWallet && (
                    <th className="px-4 py-2.5 text-right font-medium">Wallet</th>
                  )}
                  {showStatus && (
                    <th className="px-4 py-2.5 text-left font-medium">Status</th>
                  )}
                  {(canEdit || canDelete || (canRecordWalletPayment && showWallet)) && (
                    <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading && customers.length === 0 ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: tableColumnCount }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : customers.length === 0 ? (
                  <tr>
                    <td colSpan={tableColumnCount} className="px-4 py-12 text-center">
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
                      showWallet={showWallet}
                      showStatus={showStatus}
                      showCustomerType={showCustomerType}
                      canEdit={canEdit}
                      canDelete={canDelete}
                      canRecordWalletPayment={canRecordWalletPayment}
                      onEdit={() => openEdit(customer)}
                      onDelete={() => setPendingDelete(customer)}
                      onReceivePayment={() => setWalletPaymentCustomer(customer)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
        </ListPaginationRail>

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

      <ReceiveWalletPaymentDialog
        open={!!walletPaymentCustomer}
        customer={walletPaymentCustomer}
        onOpenChange={(next) => {
          if (!next) setWalletPaymentCustomer(null);
        }}
        onSuccess={(updated) => {
          setCustomers((prev) =>
            prev.map((c) => (c.id === updated.id ? { ...c, wallet_balance: updated.wallet_balance } : c))
          );
          setWalletPaymentCustomer(null);
        }}
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
  showWallet,
  showStatus,
  showCustomerType,
  canEdit,
  canDelete,
  canRecordWalletPayment,
  onEdit,
  onDelete,
  onReceivePayment,
}) {
  const outstanding = parseFloat(customer.total_outstanding || 0);
  const walletDebt = getWalletDebtAmount(customer.wallet_balance);
  const showPaymentAction = canRecordWalletPayment && walletDebt > 0;
  const hasRowActions = canEdit || canDelete || showPaymentAction;
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
      {showWallet && (
        <td className="px-4 py-3 text-right">
          <CustomerWalletBalance balance={customer.wallet_balance} />
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
      {hasRowActions && (
        <td className="px-4 py-3">
          <div className="flex items-center justify-end gap-1">
            {showPaymentAction && (
              <Button
                variant="outline"
                size="sm"
                onClick={onReceivePayment}
                aria-label="Receive wallet payment"
              >
                <Wallet className="h-3.5 w-3.5" />
                <span className="sr-only sm:not-sr-only sm:ml-1">Receive payment</span>
              </Button>
            )}
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
        className={cn(
          'left-[50%] top-[4vh] flex w-[calc(100%-2rem)] max-h-[92dvh] translate-x-[-50%] translate-y-0',
          'flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl'
        )}
        description={
          editing
            ? 'Update this customer\u2019s contact details, credit limit, and notes.'
            : 'Create a new customer profile to track sales, wallet balance, and credit.'
        }
      >
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 pr-12">
          <DialogTitle>{editing ? 'Edit customer' : 'Add customer'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={onSubmit} className="flex flex-col">
          <div
            className="dialog-form-scroll max-h-[calc(92dvh-10.5rem)] overflow-y-auto overscroll-contain px-6 py-4"
            role="region"
            aria-label="Customer details"
          >
            <div className="flex flex-col gap-4 pb-2">
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
          </div>

          <DialogFooter className="shrink-0 gap-2 border-t bg-background px-6 py-4 sm:gap-2">
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
