import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Receipt,
  TrendingDown,
  User,
  Users,
  Wallet,
} from 'lucide-react';

import { customersAPI, salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { userCanRefundSales, userCanRollbackSales, handleSaleRefundResponse } from '../../utils/saleRefund';
import { userHasAdminSaleOverride } from '../../utils/saleCompletionApproval';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import {
  formatDebtTrail,
  ledgerSourceLabel,
  standingLabel,
} from '../../utils/customerDetail';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
import { customerCommitRows } from '../../utils/formCommitSummary';
import {
  EMPTY_CUSTOMER_FORM,
  customerFormBackendErrors,
  customerFormFromRecord,
  customerSavePayload,
  validateCustomerForm,
} from '../../utils/customerFormState';
import {
  customersEnableEdit,
  customersShowCustomerType,
  customersShowNotes,
  customersShowStatus,
  customersShowTaxId,
} from '../../utils/customerDisplay';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import CommitConfirm from '../Shared/CommitConfirm';
import CenterScreenLoader from '../Shared/CenterScreenLoader';
import CustomerFormDialog from './CustomerFormDialog';

import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { CustomerWalletBalance } from './CustomerWalletBalance';
import SaleDetailDialog from '../Sales/SaleDetailDialog';
import SaleChannelIcon from '../Sales/SaleChannelIcon';
import RefundSaleDialog from '../Sales/RefundSaleDialog';
import SaleRollbackDialog from '../Sales/SaleRollbackDialog';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  SummaryCard,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ListPaginationRail,
} from '../page';
import { useListOrdering } from '../../hooks/useListOrdering';

const TABS = [
  { id: 'orders', label: 'Orders' },
  { id: 'ledger', label: 'Debt & payments' },
];

export default function CustomerDetailPage() {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') === 'ledger' ? 'ledger' : 'orders';

  const [loading, setLoading] = useState(true);
  const [payload, setPayload] = useState(null);
  const [ordersPage, setOrdersPage] = useState(1);
  const [ledgerPage, setLedgerPage] = useState(1);
  const { ordering: ordersOrdering, setOrdering: setOrdersOrdering } = useListOrdering();
  const { ordering: ledgerOrdering, setOrdering: setLedgerOrdering } = useListOrdering();
  const [selectedSale, setSelectedSale] = useState(null);
  const [saleDetailOpen, setSaleDetailOpen] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [rollbackSale, setRollbackSale] = useState(null);
  const [rollbackSubmitting, setRollbackSubmitting] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [formData, setFormData] = useState(EMPTY_CUSTOMER_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);

  const { permissions } = getStoredAuth();
  const { settings: customerModuleSettings } = useModuleSettings('customers');
  const { settings: storeSettings } = useStoreSettings();
  const canEdit = customersEnableEdit(customerModuleSettings);
  const showCustomerType = customersShowCustomerType(customerModuleSettings);
  const showTaxId = customersShowTaxId(customerModuleSettings);
  const showNotes = customersShowNotes(customerModuleSettings);
  const showStatus = customersShowStatus(customerModuleSettings, storeSettings);
  const canViewDebt = hasPermission(permissions, 'debt_management', 'view');
  const canCollect = hasPermission(permissions, 'debt_management', 'update');
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const canRollback = userCanRollbackSales(permissions);
  const canReturnForCorrection = userHasAdminSaleOverride();

  const load = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    try {
      const res = await customersAPI.detail(customerId, {
        orders_page: ordersPage,
        orders_page_size: 25,
        ledger_page: ledgerPage,
        ledger_page_size: 50,
        ...(ordersOrdering ? { orders_ordering: ordersOrdering } : {}),
        ...(ledgerOrdering ? { ledger_ordering: ledgerOrdering } : {}),
      });
      setPayload(res.data);
    } catch (err) {
      setPayload(null);
      toast.error(err.response?.data?.error || err.message || 'Could not load customer');
    } finally {
      setLoading(false);
    }
  }, [customerId, ordersPage, ledgerPage, ordersOrdering, ledgerOrdering]);

  useEffect(() => {
    load();
  }, [load]);

  const setTab = (next) => {
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      if (next === 'orders') p.delete('tab');
      else p.set('tab', next);
      return p;
    });
  };

  const customer = payload?.customer;
  const standing = payload?.standing_summary;
  const orders = payload?.orders || [];
  const ledger = payload?.ledger || [];
  const ordersPagination = payload?.orders_pagination;
  const ledgerPagination = payload?.ledger_pagination;

  const walletDebt = useMemo(
    () => getWalletDebtAmount(customer?.wallet_balance),
    [customer?.wallet_balance]
  );

  const openSale = async (order) => {
    try {
      const res = await salesAPI.get(order.id);
      setSelectedSale(res.data);
      setSaleDetailOpen(true);
    } catch (err) {
      toast.error(err.response?.data?.error || err.message);
    }
  };

  const handleRefundSubmit = async (body) => {
    if (!refundSale) return;
    setRefundSubmitting(true);
    try {
      const res = await salesAPI.refund(refundSale.id, body);
      handleSaleRefundResponse(res, {
        onApplied: () => toast.success('Sale refunded'),
        onPending: () => toast.success(pendingApprovalToastMessage()),
        onRequiresApproval: (data) => {
          toast.warning(pendingApprovalToastMessage('Sale refund', data.pending_approval_id));
        },
        onImmediate: () => toast.success('Sale refunded'),
      });
      setRefundSale(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.error || err.message);
    } finally {
      setRefundSubmitting(false);
    }
  };

  const handleRollbackSubmit = async (payload) => {
    if (!rollbackSale) return;
    setRollbackSubmitting(true);
    try {
      const res = await salesAPI.rollback(rollbackSale.id, payload);
      handleSaleRefundResponse(res, {
        onApplied: (data) => toast.success(`Sale rolled back as ${data.refund_number}`),
        onPending: () => toast.success(pendingApprovalToastMessage()),
      });
      setRollbackSale(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || 'Rollback failed');
    } finally {
      setRollbackSubmitting(false);
    }
  };

  const openEdit = async () => {
    if (!customer) return;
    setFormData(customerFormFromRecord(customer));
    setFormErrors({});
    setEditOpen(true);
    try {
      const res = await customersAPI.get(customer.id);
      setFormData(customerFormFromRecord(res.data));
    } catch (_err) {
      // Keep the profile already on screen if the full record cannot load.
    }
  };

  const updateField = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (formErrors[key]) {
      setFormErrors((prev) => ({ ...prev, [key]: '' }));
    }
  };

  const handleEditSubmit = (e) => {
    e?.preventDefault?.();
    const errors = validateCustomerForm(formData);
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error(Object.values(errors)[0]);
      return;
    }
    setShowCommitConfirm(true);
  };

  const confirmEdit = async () => {
    if (saving || !customer) return;
    setSaving(true);
    try {
      await customersAPI.update(customer.id, customerSavePayload(formData));
      toast.success('Duka updated');
      setShowCommitConfirm(false);
      setEditOpen(false);
      load();
    } catch (error) {
      const data = error.response?.data;
      const backendErrors = customerFormBackendErrors(data);
      if (backendErrors) {
        setFormErrors(backendErrors);
        toast.error(Object.values(backendErrors)[0] || 'Failed to save customer');
      } else {
        toast.error(data?.error || data?.detail || error.message || 'Failed to save customer');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading && !payload) {
    return <PageLoading rows={8} showStats />;
  }

  if (!customer) {
    return (
      <PageShell>
        <EmptyState
          icon={Users}
          title="Customer not found"
          description="This customer may have been removed or you do not have access."
          actionLabel="Back to customers"
          onAction={() => navigate('/customers')}
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title={customer.name}
        description={
          [
            customer.customer_code,
            customer.phone,
            standingLabel(customer.standing),
          ]
            .filter(Boolean)
            .join(' · ')
        }
      >
        <Button variant="outline" size="sm" asChild>
          <Link to="/customers">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Customers
          </Link>
        </Button>
        {canEdit && (
          <Button variant="outline" size="sm" onClick={openEdit}>
            <Pencil className="mr-1 h-4 w-4" />
            Edit
          </Button>
        )}
        {canViewDebt && walletDebt > 0 && (
          <Button variant="outline" size="sm" asChild>
            <Link to="/customers/debt">Debt board</Link>
          </Button>
        )}
        {canCollect && walletDebt > 0 && (
          <Button size="sm" onClick={() => setPayOpen(true)}>
            Receive payment
          </Button>
        )}
      </PageHeader>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Wallet debt"
          value={formatCurrency(standing?.wallet_debt || 0)}
          icon={TrendingDown}
          tone={walletDebt > 0 ? 'warning' : 'default'}
        />
        <SummaryCard
          label="Invoice outstanding"
          value={formatCurrency(standing?.total_outstanding || 0)}
          icon={Receipt}
        />
        <SummaryCard
          label="Lifetime sales"
          value={formatCurrency(standing?.lifetime_sales_total || 0)}
          icon={Wallet}
          subtext={`${standing?.lifetime_orders || 0} orders`}
        />
        <SummaryCard
          label="Debt collected"
          value={formatCurrency(standing?.total_debt_collected || 0)}
          icon={Users}
          subtext={`Incurred ${formatCurrency(standing?.total_debt_incurred || 0)}`}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-4">
          <div className="flex gap-1 border-b border-border">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={
                  tab === t.id
                    ? 'border-b-2 border-primary px-3 py-2 text-sm font-medium text-foreground'
                    : 'px-3 py-2 text-sm text-muted-foreground hover:text-foreground'
                }
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === 'orders' ? (
            <ListPaginationRail
              page={ordersPagination?.page || ordersPage}
              pageSize={ordersPagination?.page_size || 25}
              totalCount={ordersPagination?.count || 0}
              ordering={ordersOrdering}
              onOrderingChange={setOrdersOrdering}
              onPageChange={setOrdersPage}
            >
              {orders.length === 0 ? (
                <EmptyState
                  icon={Receipt}
                  title="No orders yet"
                  description="Sales linked to this customer will appear here."
                />
              ) : (
                <DataTable>
                  <DataTableHeader>
                    <DataTableHead sortKey="name" ordering={ordersOrdering} onOrderingChange={setOrdersOrdering}>
                      Sale
                    </DataTableHead>
                    <DataTableHead sortKey="saved" ordering={ordersOrdering} onOrderingChange={setOrdersOrdering}>
                      When
                    </DataTableHead>
                    <DataTableHead align="right">Total</DataTableHead>
                    <DataTableHead align="right">Paid</DataTableHead>
                    <DataTableHead align="right">Debt</DataTableHead>
                    <DataTableHead>Status</DataTableHead>
                  </DataTableHeader>
                  <DataTableBody>
                    {orders.map((order) => (
                      <DataTableRow
                        key={order.id}
                        className="cursor-pointer"
                        onClick={() => openSale(order)}
                      >
                        <DataTableCell className="font-medium">
                          <span className="inline-flex items-center gap-1.5">
                            <SaleChannelIcon channel={order.client_channel} />
                            {order.sale_number}
                          </span>
                        </DataTableCell>
                        <DataTableCell className="text-muted-foreground text-sm whitespace-nowrap">
                          {formatDateTime(order.occurred_at || order.created_at)}
                        </DataTableCell>
                        <DataTableCell align="right" className="tabular-nums">
                          {formatCurrency(order.total)}
                        </DataTableCell>
                        <DataTableCell align="right" className="tabular-nums">
                          {formatCurrency(order.paid_amount)}
                        </DataTableCell>
                        <DataTableCell align="right" className="tabular-nums">
                          {formatCurrency(order.debt_amount)}
                        </DataTableCell>
                        <DataTableCell>
                          <Badge
                            variant={
                              order.payment_status === 'paid' ? 'secondary' : 'destructive'
                            }
                          >
                            {order.payment_status}
                          </Badge>
                        </DataTableCell>
                      </DataTableRow>
                    ))}
                  </DataTableBody>
                </DataTable>
              )}
            </ListPaginationRail>
          ) : (
            <ListPaginationRail
              page={ledgerPagination?.page || ledgerPage}
              pageSize={ledgerPagination?.page_size || 50}
              totalCount={ledgerPagination?.count || 0}
              ordering={ledgerOrdering}
              onOrderingChange={setLedgerOrdering}
              onPageChange={setLedgerPage}
            >
              {ledger.length === 0 ? (
                <EmptyState
                  icon={Wallet}
                  title="No wallet transactions"
                  description="Debt from partial POS payments and settlements will show here."
                />
              ) : (
                <DataTable>
                  <DataTableHeader>
                    <DataTableHead sortKey="saved" ordering={ledgerOrdering} onOrderingChange={setLedgerOrdering}>
                      When
                    </DataTableHead>
                    <DataTableHead sortKey="name" ordering={ledgerOrdering} onOrderingChange={setLedgerOrdering}>
                      Type
                    </DataTableHead>
                    <DataTableHead>Debt flow</DataTableHead>
                    <DataTableHead align="right">Amount</DataTableHead>
                    <DataTableHead align="right">Balance</DataTableHead>
                  </DataTableHeader>
                  <DataTableBody>
                    {ledger.map((entry) => (
                      <DataTableRow key={entry.id}>
                        <DataTableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {formatDateTime(entry.created_at)}
                        </DataTableCell>
                        <DataTableCell>
                          <div className="font-medium text-sm">
                            {ledgerSourceLabel(entry.source_type)}
                          </div>
                          {entry.sale_number && (
                            <div className="text-xs text-muted-foreground">
                              {entry.sale_number}
                            </div>
                          )}
                        </DataTableCell>
                        <DataTableCell className="text-sm text-muted-foreground max-w-md">
                          {formatDebtTrail(entry)}
                        </DataTableCell>
                        <DataTableCell align="right" className="tabular-nums font-medium">
                          {formatCurrency(entry.amount)}
                        </DataTableCell>
                        <DataTableCell align="right" className="tabular-nums text-sm">
                          {formatCurrency(entry.balance_after)}
                        </DataTableCell>
                      </DataTableRow>
                    ))}
                  </DataTableBody>
                </DataTable>
              )}
            </ListPaginationRail>
          )}
        </div>

        <aside className="space-y-4 rounded-lg border border-border p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Profile
            </h2>
            {canEdit && (
              <Button variant="ghost" size="sm" onClick={openEdit}>
                <Pencil className="mr-1 h-3.5 w-3.5" />
                Edit
              </Button>
            )}
          </div>
          <CustomerWalletBalance balance={customer.wallet_balance} />
          <dl className="space-y-3 text-sm">
            {customer.owner_name && (
              <div className="flex gap-2">
                <User className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div>
                  <dt className="text-muted-foreground">Owner</dt>
                  <dd>{customer.owner_name}</dd>
                </div>
              </div>
            )}
            {customer.phone && (
              <div className="flex gap-2">
                <Phone className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div>
                  <dt className="text-muted-foreground">Phone</dt>
                  <dd>{customer.phone}</dd>
                </div>
              </div>
            )}
            {customer.email && (
              <div className="flex gap-2">
                <Mail className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div>
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="break-all">{customer.email}</dd>
                </div>
              </div>
            )}
            {(customer.address || customer.city) && (
              <div className="flex gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div>
                  <dt className="text-muted-foreground">Address</dt>
                  <dd>
                    {[customer.address, customer.city, customer.country]
                      .filter(Boolean)
                      .join(', ')}
                  </dd>
                </div>
              </div>
            )}
            {customer.notes && (
              <div>
                <dt className="text-muted-foreground">Notes</dt>
                <dd className="mt-1 whitespace-pre-wrap">{customer.notes}</dd>
              </div>
            )}
            {customer.contact_person && (
              <div>
                <dt className="text-muted-foreground">Contact person</dt>
                <dd className="mt-1">{customer.contact_person}</dd>
              </div>
            )}
          </dl>
        </aside>
      </section>

      <SaleDetailDialog
        sale={selectedSale}
        open={saleDetailOpen}
        onOpenChange={setSaleDetailOpen}
        canRefund={canRefund}
        canRollback={canRollback}
        canReturnForCorrection={canReturnForCorrection}
        onReturned={() => {
          setSaleDetailOpen(false);
          load();
        }}
        onRefund={(sale) => {
          setSaleDetailOpen(false);
          setRefundSale(sale);
        }}
        onRollback={(sale) => {
          setSaleDetailOpen(false);
          setRollbackSale(sale);
        }}
        onUpdated={(updated) => {
          setSelectedSale(updated);
          load();
        }}
      />

      <RefundSaleDialog
        sale={refundSale}
        open={!!refundSale}
        onOpenChange={(open) => {
          if (!open) setRefundSale(null);
        }}
        submitting={refundSubmitting}
        onSubmit={handleRefundSubmit}
      />

      <SaleRollbackDialog
        sale={rollbackSale}
        open={!!rollbackSale}
        onOpenChange={(open) => {
          if (!open) setRollbackSale(null);
        }}
        submitting={rollbackSubmitting}
        onSubmit={handleRollbackSubmit}
      />

      <CenterScreenLoader
        open={refundSubmitting || rollbackSubmitting}
        label={
          refundSubmitting
            ? 'Submitting void…'
            : rollbackSubmitting
              ? 'Submitting rollback…'
              : 'Loading…'
        }
      />

      <ReceiveWalletPaymentDialog
        open={payOpen}
        customer={customer}
        onOpenChange={setPayOpen}
        onSuccess={() => {
          setPayOpen(false);
          dispatchNavBadgesRefresh();
          load();
        }}
      />

      <CustomerFormDialog
        open={editOpen}
        onOpenChange={(next) => {
          if (saving) return;
          setEditOpen(next);
          if (!next) setShowCommitConfirm(false);
        }}
        editing={customer}
        formData={formData}
        formErrors={formErrors}
        onChange={updateField}
        onSubmit={handleEditSubmit}
        saving={saving}
        showCustomerType={showCustomerType}
        showTaxId={showTaxId}
        showNotes={showNotes}
        showStatus={showStatus}
      />
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(open) => {
          if (!open && !saving) setShowCommitConfirm(false);
        }}
        title="Update this duka?"
        description="Review the customer details, then confirm to save."
        rows={customerCommitRows(formData, { isEdit: true })}
        submitting={saving}
        confirmText="Confirm & update"
        onConfirm={confirmEdit}
      />
    </PageShell>
  );
}
