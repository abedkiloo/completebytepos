import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Banknote,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Receipt,
  Search,
  ShoppingCart,
  TrendingDown,
  Wallet,
  CheckCircle2,
} from 'lucide-react';

import { salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import {
  canViewDailySalesFromStorage,
  dailySalesCustomerPath,
} from '../../utils/dailySalesAccess';
import { userCanRefundSales, saleIsRefundable, handleSaleRefundResponse } from '../../utils/saleRefund';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import SearchableSelect from '../Shared/SearchableSelect';
import SaleDetailDialog from './SaleDetailDialog';
import RefundSaleDialog from './RefundSaleDialog';
import ReceiveWalletPaymentDialog from '../Customers/ReceiveWalletPaymentDialog';

import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  SummaryCard,
  FilterBar,
  FilterField,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ListPaginationRail,
} from '../page';

export function getTodayDateString() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function shiftDate(dateStr, offsetDays) {
  if (!dateStr) return getTodayDateString();
  const [y, m, d] = dateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  dateObj.setDate(dateObj.getDate() + offsetDays);
  const ry = dateObj.getFullYear();
  const rm = String(dateObj.getMonth() + 1).padStart(2, '0');
  const rd = String(dateObj.getDate()).padStart(2, '0');
  return `${ry}-${rm}-${rd}`;
}

export function formatDateLabel(dateStr) {
  if (!dateStr) return '';
  const todayStr = getTodayDateString();
  const yesterdayStr = shiftDate(todayStr, -1);
  const [y, m, d] = dateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  const formatted = dateObj.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  if (dateStr === todayStr) {
    return `Today · ${formatted}`;
  }
  if (dateStr === yesterdayStr) {
    return `Yesterday · ${formatted}`;
  }
  return formatted;
}

const EMPTY_SUMMARY = {
  total_sales: '0.00',
  orders_count: 0,
  total_paid: '0.00',
  paid_orders_count: 0,
  total_debt_incurred: '0.00',
  debt_orders_count: 0,
  partial_orders_count: 0,
  total_debt_collected: '0.00',
  debt_settlement_count: 0,
  total_collected: '0.00',
  payment_methods: {},
};

const EMPTY_COLLECTIONS = {
  date: '',
  count: 0,
  total: '0.00',
  results: [],
};

const ORDER_TABS = ['all', 'paid', 'debt', 'partial'];
const VALID_TABS = [...ORDER_TABS, 'collected'];

function tabFromSearchParams(searchParams) {
  const tab = searchParams.get('tab');
  return VALID_TABS.includes(tab) ? tab : 'all';
}

export default function DailySalesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDate = searchParams.get('date') || getTodayDateString();

  const [date, setDate] = useState(initialDate);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [orders, setOrders] = useState([]);
  const [collections, setCollections] = useState(EMPTY_COLLECTIONS);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [paymentStatusTab, setPaymentStatusTab] = useState(() => tabFromSearchParams(searchParams));
  const showingCollections = paymentStatusTab === 'collected';
  const [paymentMethod, setPaymentMethod] = useState('');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({
    count: 0,
    page: 1,
    page_size: 25,
    total_pages: 1,
  });

  // Modal dialog states
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [payCustomer, setPayCustomer] = useState(null);

  const { permissions } = getStoredAuth();
  const allowed = canViewDailySalesFromStorage();
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const canCollect = hasPermission(permissions, 'customers', 'update');

  const todayStr = getTodayDateString();
  const isFutureOrToday = date >= todayStr;

  // Sync date with URL params
  const handleDateChange = (newDate) => {
    setDate(newDate);
    setPage(1);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('date', newDate);
      return next;
    });
  };

  const handleTabChange = (tab) => {
    setPaymentStatusTab(tab);
    setPage(1);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tab === 'all') next.delete('tab');
      else next.set('tab', tab);
      return next;
    });
  };

  const loadDailySales = useCallback(async () => {
    if (!allowed) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const params = {
        date,
        page,
        page_size: 25,
      };
      if (!showingCollections && debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (ORDER_TABS.includes(paymentStatusTab) && paymentStatusTab !== 'all') {
        params.payment_status = paymentStatusTab;
      }
      if (!showingCollections && paymentMethod) params.payment_method = paymentMethod;
      // Sales agents: own sales only (backend also enforces).
      if (!isManagerOrAdminFromStorage()) {
        const { user } = getStoredAuth();
        if (user?.id) params.cashier_id = user.id;
      }

      const res = await salesAPI.daily(params);
      const data = res.data || {};
      setSummary(data.summary || EMPTY_SUMMARY);
      setOrders(data.orders || []);
      setCollections({ ...EMPTY_COLLECTIONS, ...(data.collections || {}) });
      if (data.pagination) {
        setPagination(data.pagination);
      }
    } catch (err) {
      toast.error('Failed to load daily sales: ' + (err.response?.data?.error || err.message));
      setOrders([]);
      setCollections(EMPTY_COLLECTIONS);
      setSummary(EMPTY_SUMMARY);
    } finally {
      setLoading(false);
    }
  }, [allowed, date, page, debouncedSearch, paymentStatusTab, paymentMethod, showingCollections]);

  useEffect(() => {
    loadDailySales();
  }, [loadDailySales]);

  const handleViewReceipt = async (order) => {
    try {
      const res = await salesAPI.get(order.id);
      setSelectedSale(res.data);
      setShowReceiptModal(true);
    } catch (err) {
      toast.error('Could not load receipt: ' + (err.response?.data?.error || err.message));
    }
  };

  const openRefundDialog = async (sale) => {
    try {
      const res = await salesAPI.get(sale.id);
      setRefundSale(res.data);
    } catch (err) {
      toast.error('Could not load sale: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleRefundSubmit = async (payload) => {
    if (!refundSale) return;
    setRefundSubmitting(true);
    try {
      const res = await salesAPI.refund(refundSale.id, payload);
      const outcome = handleSaleRefundResponse(res, {
        onRequiresApproval: (data) => {
          toast.warning(pendingApprovalToastMessage('Sale refund', data.pending_approval_id));
        },
        onImmediate: () => {
          toast.success('Sale refunded successfully');
        },
      });
      if (outcome.handled) {
        setRefundSale(null);
        loadDailySales();
        dispatchNavBadgesRefresh();
      }
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || 'Refund failed');
    } finally {
      setRefundSubmitting(false);
    }
  };

  const handlePrintReceipt = () => {
    window.print();
  };

  const formattedDateTitle = useMemo(() => formatDateLabel(date), [date]);

  const visibleCollections = useMemo(() => {
    const rows = collections.results || [];
    const query = search.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter((row) =>
      [
        row.customer_name,
        row.customer_phone,
        row.customer_code,
        row.received_by,
        row.notes,
        row.reference,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
  }, [collections.results, search]);

  if (!allowed) {
    return (
      <PageShell>
        <EmptyState
          icon={Receipt}
          title="Daily Sales is restricted"
          description="Ask a Super Admin to grant the sales.daily_sales permission for your role."
          actionLabel="Back to Sales History"
          onAction={() => {
            window.location.assign('/sales');
          }}
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title="Daily Sales Tracker"
        description={
          isManagerOrAdminFromStorage()
            ? 'Monitor daily sales revenue, upfront payments collected, and credit orders taken as debt.'
            : 'Your sales only — revenue, payments collected, and credit you booked today.'
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" asChild>
            <Link to="/sales">
              <Receipt className="h-4 w-4 mr-1.5" />
              Sales History
            </Link>
          </Button>
          <Button asChild>
            <Link to="/pos">
              <ShoppingCart className="h-4 w-4 mr-1.5" />
              Open POS
            </Link>
          </Button>
        </div>
      </PageHeader>

      {/* Date Navigation Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDateChange(shiftDate(date, -1))}
            title="Previous Day"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="hidden sm:inline ml-1">Previous day</span>
          </Button>
          <div className="flex items-center gap-2">
            <Input
              type="date"
              value={date}
              onChange={(e) => handleDateChange(e.target.value)}
              className="h-9 w-auto text-sm font-medium"
            />
            {date !== todayStr && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleDateChange(todayStr)}
              >
                Today
              </Button>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleDateChange(shiftDate(date, 1))}
            disabled={isFutureOrToday}
            title="Next Day"
          >
            <span className="hidden sm:inline mr-1">Next day</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Calendar className="h-4 w-4 text-primary" />
          <span>{formattedDateTitle}</span>
        </div>
      </div>

      {/* Daily Summary Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={Receipt}
          label="Total Sales"
          value={formatCurrency(summary.total_sales)}
          subtext={`${summary.orders_count} completed orders`}
        />
        <SummaryCard
          icon={CheckCircle2}
          label="Paid at Checkout"
          value={formatCurrency(summary.total_paid)}
          subtext={`${summary.paid_orders_count} fully paid orders`}
          tone="success"
        />
        <SummaryCard
          icon={TrendingDown}
          label="Taken as Debt"
          value={formatCurrency(summary.total_debt_incurred)}
          subtext={`${summary.debt_orders_count} debt orders (${summary.partial_orders_count} partial)`}
          tone={Number(summary.total_debt_incurred) > 0 ? 'destructive' : 'default'}
        />
        <SummaryCard
          icon={Wallet}
          label="Prior Debt Collected"
          value={formatCurrency(summary.total_debt_collected)}
          subtext={`${summary.debt_settlement_count} payment${summary.debt_settlement_count === 1 ? '' : 's'} · tap to see who paid`}
          tone={Number(summary.total_debt_collected) > 0 ? 'success' : 'default'}
          onClick={() => handleTabChange('collected')}
        />
      </div>

      {/* Cash Flow Reconciliation Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 px-4 py-2.5 text-xs sm:text-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-medium">Total Cash/Tender In Today:</span>
          <span className="font-bold text-success text-base">{formatCurrency(summary.total_collected)}</span>
          <span className="text-muted-foreground text-xs">(Sales tender + Debt collections)</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {Object.entries(summary.payment_methods || {}).map(([m, val]) => (
            <Badge key={m} variant="outline" className="text-xs uppercase">
              {m}: {formatCurrency(val.total)}
            </Badge>
          ))}
        </div>
      </div>

      {/* Tabs & Filters */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
          <div className="flex flex-wrap gap-1">
            <Button
              variant={paymentStatusTab === 'all' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleTabChange('all')}
            >
              All Orders ({summary.orders_count})
            </Button>
            <Button
              variant={paymentStatusTab === 'paid' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleTabChange('paid')}
            >
              Fully Paid ({summary.paid_orders_count})
            </Button>
            <Button
              variant={paymentStatusTab === 'debt' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleTabChange('debt')}
            >
              Taken as Debt ({summary.debt_orders_count})
            </Button>
            <Button
              variant={paymentStatusTab === 'partial' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleTabChange('partial')}
            >
              Partial Only ({summary.partial_orders_count})
            </Button>
            <Button
              variant={showingCollections ? 'default' : 'ghost'}
              size="sm"
              onClick={() => handleTabChange('collected')}
            >
              Debt collected ({summary.debt_settlement_count})
            </Button>
          </div>

          <div className="text-xs text-muted-foreground">
            {showingCollections
              ? `Showing ${visibleCollections.length} of ${collections.count} payments`
              : `Showing ${orders.length} of ${pagination.count} matching orders`}
          </div>
        </div>

        <FilterBar>
          <FilterField label="Search" className="min-w-[220px] flex-[2]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder={
                  showingCollections ? 'Search customer, staff, notes…' : 'Search sale #, customer, cashier…'
                }
                className="h-10 pl-9"
              />
            </div>
          </FilterField>
          {!showingCollections ? (
          <FilterField label="Payment Method">
            <SearchableSelect
              value={paymentMethod}
              onChange={(e) => {
                setPaymentMethod(e.target.value);
                setPage(1);
              }}
              options={[
                { id: '', name: 'All payment methods' },
                { id: 'cash', name: 'Cash' },
                { id: 'mpesa', name: 'M-PESA' },
                { id: 'card', name: 'Card' },
                { id: 'other', name: 'Other' },
              ]}
              placeholder="All methods"
            />
          </FilterField>
          ) : null}
        </FilterBar>
      </div>

      {showingCollections ? (
        loading && visibleCollections.length === 0 && collections.count === 0 ? (
          <PageLoading rows={6} />
        ) : visibleCollections.length === 0 ? (
          <EmptyState
            icon={Banknote}
            title="No collections on this day"
            description={
              search
                ? 'Try adjusting your search query.'
                : `No debt payments recorded for ${formattedDateTitle}.`
            }
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Time</DataTableHead>
              <DataTableHead>Customer</DataTableHead>
              <DataTableHead align="right">Amount paid</DataTableHead>
              <DataTableHead align="right">Balance after</DataTableHead>
              <DataTableHead>Received by</DataTableHead>
              <DataTableHead>Notes</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {visibleCollections.map((row) => {
                const remaining = Number(row.balance_after);
                const stillOwes = !Number.isNaN(remaining) && remaining < 0;
                return (
                  <DataTableRow key={row.id}>
                    <DataTableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {row.created_at ? formatDateTime(row.created_at) : '—'}
                    </DataTableCell>
                    <DataTableCell>
                      {row.customer_id ? (
                        <>
                          <Link
                            to={dailySalesCustomerPath(row.customer_id, date)}
                            className="font-medium text-primary hover:underline"
                          >
                            {row.customer_name || 'Customer'}
                          </Link>
                          <div className="text-xs text-muted-foreground">
                            {[row.customer_phone, row.customer_code].filter(Boolean).join(' · ') ||
                              '—'}
                          </div>
                        </>
                      ) : (
                        <span className="text-muted-foreground text-xs italic">Customer</span>
                      )}
                    </DataTableCell>
                    <DataTableCell align="right" className="font-semibold text-success">
                      {formatCurrency(row.amount)}
                    </DataTableCell>
                    <DataTableCell
                      align="right"
                      className={
                        stillOwes ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'
                      }
                    >
                      {stillOwes ? formatCurrency(Math.abs(remaining)) : 'Settled'}
                    </DataTableCell>
                    <DataTableCell className="text-sm text-muted-foreground">
                      {row.received_by || '—'}
                    </DataTableCell>
                    <DataTableCell className="max-w-[16rem] truncate text-sm text-muted-foreground">
                      {[row.reference, row.notes].filter(Boolean).join(' · ') || '—'}
                    </DataTableCell>
                  </DataTableRow>
                );
              })}
            </DataTableBody>
          </DataTable>
        )
      ) : loading && orders.length === 0 ? (
        <PageLoading rows={6} />
      ) : orders.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={`No ${paymentStatusTab === 'debt' ? 'debt ' : paymentStatusTab === 'paid' ? 'paid ' : ''}orders found`}
          description={
            search || paymentMethod
              ? 'Try adjusting your search query or filters.'
              : `No orders recorded for ${formattedDateTitle}. Try navigating to another date.`
          }
          actionLabel="Open POS"
          onAction={() => window.location.assign('/pos')}
        />
      ) : (
        <ListPaginationRail
          page={page}
          pageSize={pagination.page_size}
          totalCount={pagination.count}
          suffix={`${pagination.count} orders`}
          onPageChange={setPage}
        >
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Sale #</DataTableHead>
              <DataTableHead>Customer</DataTableHead>
              <DataTableHead>Staff</DataTableHead>
              <DataTableHead align="right">Total</DataTableHead>
              <DataTableHead align="right">Paid Upfront</DataTableHead>
              <DataTableHead align="right">Debt Taken</DataTableHead>
              <DataTableHead>Payment Status</DataTableHead>
              <DataTableHead>Method</DataTableHead>
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {orders.map((order) => {
                const isDebt = order.payment_status === 'debt';
                const isPartial = order.payment_status === 'partial';
                const isPaid = order.payment_status === 'paid';

                return (
                  <DataTableRow key={order.id}>
                    <DataTableCell>
                      <button
                        type="button"
                        className="font-medium text-primary hover:underline text-left block"
                        onClick={() => handleViewReceipt(order)}
                      >
                        {order.sale_number}
                      </button>
                      <div className="text-xs text-muted-foreground whitespace-nowrap">
                        {order.occurred_at ? formatDateTime(order.occurred_at) : '—'}
                      </div>
                      {order.is_late_entry ? (
                        <Badge variant="outline" className="mt-0.5 text-[10px]">
                          Late entry
                        </Badge>
                      ) : null}
                    </DataTableCell>

                    <DataTableCell>
                      {order.customer ? (
                        <div>
                          <Link
                            to={dailySalesCustomerPath(order.customer.id, date)}
                            className="font-medium text-primary hover:underline"
                          >
                            {order.customer.name}
                          </Link>
                          <div className="text-xs text-muted-foreground">
                            {[order.customer.phone, order.customer.customer_code]
                              .filter(Boolean)
                              .join(' · ')}
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-xs italic">Walk-in Customer</span>
                      )}
                    </DataTableCell>

                    <DataTableCell className="text-sm">
                      {order.served_by_name || order.cashier_name || '—'}
                    </DataTableCell>

                    <DataTableCell align="right" className="font-semibold">
                      {formatCurrency(order.total)}
                    </DataTableCell>

                    <DataTableCell align="right" className={isPaid ? 'text-success font-medium' : ''}>
                      {formatCurrency(order.paid_amount)}
                    </DataTableCell>

                    <DataTableCell align="right">
                      {Number(order.debt_amount) > 0 ? (
                        <span className="font-bold text-destructive">
                          {formatCurrency(order.debt_amount)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </DataTableCell>

                    <DataTableCell>
                      {isPaid && (
                        <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
                          Paid
                        </Badge>
                      )}
                      {isDebt && (
                        <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive">
                          Debt (Unpaid)
                        </Badge>
                      )}
                      {isPartial && (
                        <Badge variant="outline" className="border-amber-500/30 bg-amber-500/10 text-amber-600">
                          Partial Debt
                        </Badge>
                      )}
                    </DataTableCell>

                    <DataTableCell>
                      <Badge variant="secondary" className="capitalize">
                        {order.payment_method}
                      </Badge>
                      {order.payment_reference ? (
                        <div className="mt-0.5 text-[11px] text-muted-foreground font-mono">
                          {order.payment_reference}
                        </div>
                      ) : null}
                    </DataTableCell>

                    <DataTableCell align="right">
                      <div className="flex flex-wrap justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewReceipt(order)}
                        >
                          Receipt
                        </Button>
                        {canCollect && Number(order.debt_amount) > 0 && order.customer && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() =>
                              setPayCustomer({
                                id: order.customer.id,
                                name: order.customer.name,
                                phone: order.customer.phone,
                                wallet_balance: order.customer.wallet_balance,
                              })
                            }
                          >
                            Settle
                          </Button>
                        )}
                        {order.customer ? (
                          <Button variant="outline" size="sm" asChild>
                            <Link to={dailySalesCustomerPath(order.customer.id, date)}>
                              View day
                            </Link>
                          </Button>
                        ) : null}
                      </div>
                    </DataTableCell>
                  </DataTableRow>
                );
              })}
            </DataTableBody>
          </DataTable>
        </ListPaginationRail>
      )}

      {/* Modals */}
      <SaleDetailDialog
        sale={selectedSale}
        open={showReceiptModal}
        onOpenChange={setShowReceiptModal}
        canRefund={canRefund}
        onRefund={(sale) => {
          setShowReceiptModal(false);
          openRefundDialog(sale);
        }}
        onPrint={handlePrintReceipt}
      />

      <RefundSaleDialog
        sale={refundSale}
        open={Boolean(refundSale)}
        onOpenChange={(open) => !open && setRefundSale(null)}
        onSubmit={handleRefundSubmit}
        submitting={refundSubmitting}
      />

      <ReceiveWalletPaymentDialog
        open={Boolean(payCustomer)}
        customer={payCustomer}
        onOpenChange={(open) => {
          if (!open) setPayCustomer(null);
        }}
        onSuccess={() => {
          setPayCustomer(null);
          loadDailySales();
          dispatchNavBadgesRefresh();
        }}
      />
    </PageShell>
  );
}
