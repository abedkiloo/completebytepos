import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Banknote,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  Receipt,
  Search,
  ShoppingCart,
  TrendingDown,
  Wallet,
  CheckCircle2,
} from 'lucide-react';

import { salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import {
  settlementMethodLabel,
  settlementReferenceLabel,
} from '../../utils/debtManagement';
import { toast } from '../../utils/toast';
import {
  getStoredAuth,
  hasPermission,
  userSeesAllSalesFromStorage,
} from '../../utils/roleAccess';
import {
  canViewDailySalesFromStorage,
  dailySalesCustomerPath,
} from '../../utils/dailySalesAccess';
import { userCanRefundSales, userCanUnvoidSales, handleSaleRefundResponse, userCanRollbackSales } from '../../utils/saleRefund';
import { userHasAdminSaleOverride } from '../../utils/saleCompletionApproval';
import { saleCancellationPendingToastMessage } from '../../utils/makerChecker';
import CenterScreenLoader from '../Shared/CenterScreenLoader';
import SaleChannelIcon from './SaleChannelIcon';
import SaleOriginBadge from './SaleOriginBadge';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useSellerOptions } from '../../hooks/useSellerOptions';
import { useListOrdering } from '../../hooks/useListOrdering';
import { withListOrdering } from '../../utils/listOrdering';
import { saleFinalStatusLabel, saleStatusBadgeTone } from '../../utils/saleItemDisplay';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import SearchableSelect from '../Shared/SearchableSelect';
import SaleDetailDialog from './SaleDetailDialog';
import RefundSaleDialog from './RefundSaleDialog';
import SaleRollbackDialog from './SaleRollbackDialog';
import ReceiveWalletPaymentDialog from '../Customers/ReceiveWalletPaymentDialog';
import CheckpointMarkersStrip from '../Inventory/CheckpointMarkersStrip';

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

/** Paid vs debt shares of the day's goods sold (for the mix progress bar). */
export function dailySalesPaidDebtMix(summary) {
  const total = Math.max(0, Number(summary?.total_sales) || 0);
  const paid = Math.max(0, Number(summary?.total_paid) || 0);
  const debt = Math.max(0, Number(summary?.total_debt_incurred) || 0);
  if (total <= 0) {
    return { total: 0, paid: 0, debt: 0, paidPct: 0, debtPct: 0 };
  }
  const paidPct = Math.min(100, (paid / total) * 100);
  const debtPct = Math.min(100 - paidPct, (debt / total) * 100);
  return { total, paid, debt, paidPct, debtPct };
}

function paymentStatusTone(status) {
  if (status === 'paid') return 'success';
  if (status === 'partial') return 'warning';
  if (status === 'debt') return 'destructive';
  if (status === 'needs_correction') return 'warning';
  return 'secondary';
}

function paymentStatusLabel(status) {
  if (status === 'paid') return 'Paid';
  if (status === 'partial') return 'Partial';
  if (status === 'debt') return 'Debt';
  if (status === 'needs_correction') return 'Needs correction';
  return status || '—';
}

function PaidDebtMixBar({ paidPct, debtPct, paidLabel, debtLabel, className = '' }) {
  const hasMix = paidPct > 0 || debtPct > 0;
  return (
    <div className={className} data-testid="daily-paid-debt-bar">
      <div
        className="flex h-3 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={
          hasMix
            ? `Paid ${Math.round(paidPct)} percent, debt ${Math.round(debtPct)} percent`
            : 'No sales yet'
        }
      >
        {paidPct > 0 ? (
          <div
            className="h-full bg-emerald-500 transition-[width]"
            style={{ width: `${paidPct}%` }}
            data-testid="daily-paid-segment"
          />
        ) : null}
        {debtPct > 0 ? (
          <div
            className="h-full bg-rose-500 transition-[width]"
            style={{ width: `${debtPct}%` }}
            data-testid="daily-debt-segment"
          />
        ) : null}
      </div>
      {(paidLabel || debtLabel) ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          {paidLabel ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700 dark:text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
              {paidLabel}
            </span>
          ) : null}
          {debtLabel ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-rose-700 dark:text-rose-400">
              <span className="h-2 w-2 rounded-full bg-rose-500" aria-hidden />
              {debtLabel}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function DailySalesPage() {
  const navigate = useNavigate();
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
  const [sellerId, setSellerId] = useState('');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({
    count: 0,
    page: 1,
    page_size: 25,
    total_pages: 1,
  });
  const { ordering, setOrdering } = useListOrdering();

  // Modal dialog states
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [rollbackSale, setRollbackSale] = useState(null);
  const [rollbackSubmitting, setRollbackSubmitting] = useState(false);
  const [payCustomer, setPayCustomer] = useState(null);

  const { permissions } = getStoredAuth();
  const allowed = canViewDailySalesFromStorage();
  const isAdmin = userHasAdminSaleOverride();
  const canRefund = userCanRefundSales(permissions, { isAdmin });
  const canRollback = userCanRollbackSales(permissions);
  const canUnvoid = userCanUnvoidSales(permissions, { isAdmin });
  const canReturnForCorrection = isAdmin;
  const canCollect = hasPermission(permissions, 'customers', 'update');
  const canFilterBySeller = userSeesAllSalesFromStorage();
  const sellerOptions = useSellerOptions(allowed && canFilterBySeller);

  const todayStr = getTodayDateString();
  const isFutureOrToday = date >= todayStr;
  const paidDebtMix = useMemo(() => dailySalesPaidDebtMix(summary), [summary]);

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
      const params = withListOrdering({
        date,
        page,
        page_size: 25,
      }, ordering);
      if (!showingCollections && debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (ORDER_TABS.includes(paymentStatusTab) && paymentStatusTab !== 'all') {
        params.payment_status = paymentStatusTab;
      }
      if (!showingCollections && paymentMethod) params.payment_method = paymentMethod;
      // Own sales only unless admin / manager / sales.view_all (backend also enforces).
      if (!canFilterBySeller) {
        const { user } = getStoredAuth();
        if (user?.id) params.cashier_id = user.id;
      } else if (!showingCollections && sellerId) {
        params.cashier_id = sellerId;
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
  }, [allowed, date, page, debouncedSearch, paymentStatusTab, paymentMethod, showingCollections, ordering, canFilterBySeller, sellerId]);

  useEffect(() => {
    loadDailySales();
  }, [loadDailySales]);

  const openSaleForCorrection = (order) => {
    setShowReceiptModal(false);
    setSelectedSale(null);
    navigate(`/pos/billing?sale=${order.id}`);
  };

  const handleViewReceipt = async (order) => {
    // Returned sales need the rectify Terminal — not a receipt popup that blocks edits.
    if (
      order?.payment_status === 'needs_correction'
      || order?.needs_salesperson_action
      || order?.status === 'holding'
    ) {
      openSaleForCorrection(order);
      return;
    }
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
      handleSaleRefundResponse(res, {
        onApplied: () => toast.success('Sale refunded successfully'),
        onPending: () => toast.success(saleCancellationPendingToastMessage()),
      });
      setRefundSale(null);
      loadDailySales();
      dispatchNavBadgesRefresh();
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || 'Refund failed');
    } finally {
      setRefundSubmitting(false);
    }
  };

  const openRollbackDialog = async (sale) => {
    try {
      const res = await salesAPI.get(sale.id);
      setRollbackSale(res.data);
    } catch (err) {
      toast.error('Could not load sale: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleRollbackSubmit = async (payload) => {
    if (!rollbackSale) return;
    setRollbackSubmitting(true);
    try {
      const res = await salesAPI.rollback(rollbackSale.id, payload);
      handleSaleRefundResponse(res, {
        onApplied: (data) => toast.success(`Sale rolled back as ${data.refund_number}`),
        onPending: () => toast.success(saleCancellationPendingToastMessage()),
      });
      setRollbackSale(null);
      loadDailySales();
      dispatchNavBadgesRefresh();
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || 'Rollback failed');
    } finally {
      setRollbackSubmitting(false);
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
          description="Your role cannot view sales. Ask an admin to grant sales.view for your role."
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
      <CheckpointMarkersStrip className="mb-1" />
      <PageHeader
        title="Daily Sales Tracker"
        description={
          userSeesAllSalesFromStorage()
            ? 'Monitor daily sales revenue, upfront payments collected, and credit orders taken as debt.'
            : 'Your sales only — pick any day to see your revenue, payments collected, and credit booked.'
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

      {Number(summary.pending_approval_count) > 0 ? (
        <div
          className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm text-sky-950"
          data-testid="daily-pending-approval"
        >
          <Clock className="h-4 w-4 shrink-0" />
          <span className="font-semibold">
            {summary.pending_approval_count} sale{Number(summary.pending_approval_count) === 1 ? '' : 's'} awaiting approval
          </span>
          <span>
            · {formatCurrency(summary.pending_approval_total)} ({formatCurrency(summary.pending_approval_paid)} already collected)
          </span>
          <span className="text-xs text-sky-900">
            Not in the totals below until a manager approves.
          </span>
        </div>
      ) : null}

      {/* Daily Summary Cards — each opens the matching list below */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={Receipt}
          label="Total Sales"
          value={formatCurrency(summary.total_sales)}
          subtext={
            Number(summary.field_orders_count) > 0
              ? `${summary.orders_count} completed · ${summary.shop_orders_count} shop, ${summary.field_orders_count} field (${formatCurrency(summary.field_sales_total)}) · tap to view`
              : `${summary.orders_count} completed orders · tap to view`
          }
          onClick={() => handleTabChange('all')}
        />
        <SummaryCard
          icon={CheckCircle2}
          label="Paid at Checkout"
          value={formatCurrency(summary.total_paid)}
          subtext={`${summary.paid_orders_count} fully paid orders · tap to view`}
          tone="success"
          onClick={() => handleTabChange('paid')}
        />
        <SummaryCard
          icon={TrendingDown}
          label="Taken as Debt"
          value={formatCurrency(summary.total_debt_incurred)}
          subtext={`${summary.debt_orders_count} debt orders (${summary.partial_orders_count} partial) · tap to view`}
          tone={Number(summary.total_debt_incurred) > 0 ? 'destructive' : 'default'}
          onClick={() => handleTabChange('debt')}
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

      {/* Paid (green) vs debt (rose) share of today's goods sold */}
      <div className="rounded-xl border bg-card p-3 shadow-xs sm:p-4">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-foreground">Paid vs debt on goods sold</p>
            <p className="text-xs text-muted-foreground">
              Green is money taken at checkout; rose is still on the customer’s account.
            </p>
          </div>
          <p className="text-xs tabular-nums text-muted-foreground">
            {Math.round(paidDebtMix.paidPct)}% paid · {Math.round(paidDebtMix.debtPct)}% in debt
          </p>
        </div>
        <PaidDebtMixBar
          paidPct={paidDebtMix.paidPct}
          debtPct={paidDebtMix.debtPct}
          paidLabel={`Paid ${formatCurrency(paidDebtMix.paid)}`}
          debtLabel={`Debt ${formatCurrency(paidDebtMix.debt)}`}
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
          <FilterField label="Search" className="min-w-[12rem] flex-1 sm:min-w-[14rem]">
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
              ]}
              placeholder="All methods"
            />
          </FilterField>
          ) : null}
          {!showingCollections && canFilterBySeller ? (
          <FilterField label="Sold by">
            <SearchableSelect
              value={sellerId}
              onChange={(e) => {
                setSellerId(e.target.value);
                setPage(1);
              }}
              options={[{ id: '', name: 'Everyone' }, ...sellerOptions]}
              placeholder="Everyone"
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
              <DataTableHead>Method</DataTableHead>
              <DataTableHead>Reference</DataTableHead>
              <DataTableHead>Collected by</DataTableHead>
              <DataTableHead align="right">Balance after</DataTableHead>
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
                    <DataTableCell className="text-sm font-medium">
                      {settlementMethodLabel(row)}
                    </DataTableCell>
                    <DataTableCell className="font-mono text-sm">
                      {settlementReferenceLabel(row)}
                    </DataTableCell>
                    <DataTableCell className="text-sm text-muted-foreground">
                      {row.received_by || '—'}
                    </DataTableCell>
                    <DataTableCell
                      align="right"
                      className={
                        stillOwes ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'
                      }
                    >
                      {stillOwes ? formatCurrency(Math.abs(remaining)) : 'Settled'}
                    </DataTableCell>
                    <DataTableCell className="max-w-[12rem] truncate text-sm text-muted-foreground">
                      {row.notes || '—'}
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
          ordering={ordering}
          onOrderingChange={setOrdering}
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
                const payStatus = order.payment_status;
                const rowMix = dailySalesPaidDebtMix({
                  total_sales: order.total,
                  total_paid: order.paid_amount ?? order.amount_paid,
                  total_debt_incurred: order.debt_amount,
                });
                const debtTaken = Number(order.debt_amount) > 0;
                const paidUpfront = Number(order.paid_amount ?? order.amount_paid) > 0;
                const rowTone =
                  payStatus === 'debt'
                    ? 'bg-rose-50/70 dark:bg-rose-950/20'
                    : payStatus === 'partial' || payStatus === 'needs_correction'
                      ? 'bg-amber-50/60 dark:bg-amber-950/15'
                      : '';

                return (
                  <DataTableRow key={order.id} className={rowTone}>
                    <DataTableCell>
                      <button
                        type="button"
                        className="font-medium text-primary hover:underline text-left inline-flex items-center gap-1.5"
                        onClick={() => handleViewReceipt(order)}
                      >
                        <SaleChannelIcon channel={order.client_channel} />
                        {order.sale_number}
                      </button>
                      <SaleOriginBadge sale={order} className="ml-1" />
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
                      <div>{formatCurrency(order.total)}</div>
                      <PaidDebtMixBar
                        className="mt-1.5 min-w-[5.5rem]"
                        paidPct={rowMix.paidPct}
                        debtPct={rowMix.debtPct}
                      />
                    </DataTableCell>

                    <DataTableCell
                      align="right"
                      className={
                        paidUpfront
                          ? 'font-semibold tabular-nums text-emerald-700 dark:text-emerald-400'
                          : 'text-muted-foreground'
                      }
                    >
                      {paidUpfront ? formatCurrency(order.paid_amount) : '—'}
                    </DataTableCell>

                    <DataTableCell align="right">
                      {debtTaken ? (
                        <span className="font-bold tabular-nums text-rose-700 dark:text-rose-400">
                          {formatCurrency(order.debt_amount)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </DataTableCell>

                    <DataTableCell>
                      <div className="flex flex-col items-start gap-1">
                        <Badge variant={paymentStatusTone(payStatus)}>
                          {paymentStatusLabel(payStatus)}
                        </Badge>
                        {['cancelled', 'rejected', 'holding', 'pending'].includes(
                          saleStatusBadgeTone(order),
                        ) ? (
                          <span className="text-[10px] text-muted-foreground">
                            {saleFinalStatusLabel(order)}
                          </span>
                        ) : null}
                      </div>
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
                        {payStatus === 'needs_correction' || order.needs_salesperson_action ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openSaleForCorrection(order)}
                          >
                            Fix on Terminal
                          </Button>
                        ) : null}
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
        canRollback={canRollback}
        canUnvoid={canUnvoid}
        canReturnForCorrection={canReturnForCorrection}
        onReturned={() => {
          setShowReceiptModal(false);
          loadDailySales();
        }}
        onUnvoided={(updated) => {
          setSelectedSale(updated);
          loadDailySales();
        }}
        onRefund={(sale) => {
          setShowReceiptModal(false);
          openRefundDialog(sale);
        }}
        onRollback={(sale) => {
          setShowReceiptModal(false);
          openRollbackDialog(sale);
        }}
        onPrint={handlePrintReceipt}
        onUpdated={(updated) => {
          setSelectedSale(updated);
          loadDailySales();
        }}
      />

      <RefundSaleDialog
        sale={refundSale}
        open={Boolean(refundSale)}
        onOpenChange={(open) => !open && setRefundSale(null)}
        onSubmit={handleRefundSubmit}
        submitting={refundSubmitting}
      />

      <SaleRollbackDialog
        sale={rollbackSale}
        open={Boolean(rollbackSale)}
        onOpenChange={(open) => !open && setRollbackSale(null)}
        onSubmit={handleRollbackSubmit}
        submitting={rollbackSubmitting}
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

      <CenterScreenLoader
        open={refundSubmitting || rollbackSubmitting}
        label={
          refundSubmitting
            ? 'Submitting void for approval…'
            : rollbackSubmitting
              ? 'Submitting rollback for approval…'
              : 'Loading…'
        }
      />
    </PageShell>
  );
}
