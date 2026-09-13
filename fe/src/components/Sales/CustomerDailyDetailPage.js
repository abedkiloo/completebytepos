import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  Mail,
  MapPin,
  Phone,
  Receipt,
  TrendingDown,
  Users,
  Wallet,
} from 'lucide-react';

import { salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import {
  canViewDailySalesFromStorage,
  dailySalesListPath,
  dayStandingLabel,
} from '../../utils/dailySalesAccess';
import { getTodayDateString, formatDateLabel, shiftDate } from './DailySalesPage';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { userCanRefundSales, handleSaleRefundResponse } from '../../utils/saleRefund';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';

import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import SaleDetailDialog from './SaleDetailDialog';
import RefundSaleDialog from './RefundSaleDialog';
import ReceiveWalletPaymentDialog from '../Customers/ReceiveWalletPaymentDialog';
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
} from '../page';

const EMPTY_DAY = {
  orders_count: 0,
  total_sales: '0.00',
  total_paid: '0.00',
  total_debt_incurred: '0.00',
  paid_orders_count: 0,
  debt_orders_count: 0,
  partial_orders_count: 0,
  debt_collected: '0.00',
  day_standing: 'good',
};

export default function CustomerDailyDetailPage() {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const date = searchParams.get('date') || getTodayDateString();

  const [loading, setLoading] = useState(true);
  const [payload, setPayload] = useState(null);
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceipt, setShowReceipt] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [payOpen, setPayOpen] = useState(false);

  const allowed = canViewDailySalesFromStorage();
  const { permissions } = getStoredAuth();
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const canCollect = hasPermission(permissions, 'customers', 'update');

  const load = useCallback(async () => {
    if (!allowed || !customerId) return;
    setLoading(true);
    try {
      const res = await salesAPI.dailyCustomer(customerId, { date });
      setPayload(res.data);
    } catch (err) {
      setPayload(null);
      toast.error(err.response?.data?.error || err.message || 'Could not load customer day');
    } finally {
      setLoading(false);
    }
  }, [allowed, customerId, date]);

  useEffect(() => {
    load();
  }, [load]);

  const setDate = (next) => {
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev);
      p.set('date', next);
      return p;
    });
  };

  const customer = payload?.customer;
  const daySummary = payload?.day_summary || EMPTY_DAY;
  const standing = payload?.standing_summary;
  const orders = payload?.orders || [];
  const dateLabel = useMemo(() => formatDateLabel(date), [date]);
  const todayStr = getTodayDateString();

  const openReceipt = async (order) => {
    try {
      const res = await salesAPI.get(order.id);
      setSelectedSale(res.data);
      setShowReceipt(true);
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

  if (!allowed) {
    return (
      <PageShell>
        <EmptyState
          icon={Receipt}
          title="Daily Sales is restricted"
          description="Ask a Super Admin to grant the sales.daily_sales permission for your role."
          actionLabel="Back to Sales History"
          onAction={() => navigate('/sales')}
        />
      </PageShell>
    );
  }

  if (loading && !payload) {
    return <PageLoading rows={8} />;
  }

  if (!customer) {
    return (
      <PageShell>
        <EmptyState
          icon={Users}
          title="Customer not found"
          description="This customer may have been removed, or the link is invalid."
          actionLabel="Back to Daily Sales"
          onAction={() => navigate(dailySalesListPath(date))}
        />
      </PageShell>
    );
  }

  const standingTone =
    customer.standing === 'debt' ? 'destructive' : 'success';

  return (
    <PageShell>
      <PageHeader
        title={customer.name}
        description={`${customer.customer_code}${customer.phone ? ` · ${customer.phone}` : ''}`}
      >
        <Button variant="outline" asChild>
          <Link to={dailySalesListPath(date)}>
            <ArrowLeft className="mr-1.5 h-4 w-4" />
            Daily Sales
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to={`/customers/${customer.id}`}>Full profile</Link>
        </Button>
        {canCollect && Number(customer.wallet_debt) > 0 ? (
          <Button onClick={() => setPayOpen(true)}>
            <Wallet className="mr-1.5 h-4 w-4" />
            Receive payment
          </Button>
        ) : null}
      </PageHeader>

      {/* Breadcrumb mental model */}
      <nav className="text-sm text-muted-foreground" aria-label="Breadcrumb">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link className="hover:text-foreground" to={dailySalesListPath(date)}>
              Daily Sales
            </Link>
          </li>
          <li aria-hidden>/</li>
          <li className="font-medium text-foreground">{customer.name}</li>
          <li aria-hidden>·</li>
          <li>{dateLabel}</li>
        </ol>
      </nav>

      {/* Identity + standing — one focused band */}
      <section className="rounded-xl border bg-card p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold tracking-tight">{customer.name}</h2>
              <Badge
                variant="outline"
                className={
                  standingTone === 'destructive'
                    ? 'border-destructive/30 bg-destructive/10 text-destructive'
                    : 'border-success/30 bg-success/10 text-success'
                }
              >
                {customer.standing === 'debt' ? 'Has open debt' : 'Good standing'}
              </Badge>
              {!customer.is_active ? (
                <Badge variant="secondary">Inactive</Badge>
              ) : null}
            </div>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {customer.phone ? (
                <li className="flex items-center gap-2">
                  <Phone className="h-3.5 w-3.5" />
                  {customer.phone}
                </li>
              ) : null}
              {customer.email ? (
                <li className="flex items-center gap-2">
                  <Mail className="h-3.5 w-3.5" />
                  {customer.email}
                </li>
              ) : null}
              {(customer.city || customer.address) ? (
                <li className="flex items-center gap-2">
                  <MapPin className="h-3.5 w-3.5" />
                  {[customer.address, customer.city].filter(Boolean).join(', ')}
                </li>
              ) : null}
            </ul>
          </div>
          <div className="rounded-lg border bg-muted/20 px-4 py-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Account balance
            </p>
            <p
              className={`mt-1 text-2xl font-bold tabular-nums ${
                Number(customer.wallet_debt) > 0 ? 'text-destructive' : 'text-foreground'
              }`}
            >
              {Number(customer.wallet_debt) > 0
                ? `Owes ${formatCurrency(customer.wallet_debt)}`
                : Number(customer.wallet_credit) > 0
                  ? `Credit ${formatCurrency(customer.wallet_credit)}`
                  : formatCurrency(0)}
            </p>
          </div>
        </div>
      </section>

      {/* Day picker — keep navigation light */}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => setDate(shiftDate(date, -1))}>
          Previous day
        </Button>
        <Input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="h-9 w-auto"
        />
        {date !== todayStr ? (
          <Button variant="secondary" size="sm" onClick={() => setDate(todayStr)}>
            Today
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          disabled={date >= todayStr}
          onClick={() => setDate(shiftDate(date, 1))}
        >
          Next day
        </Button>
        <span className="ml-auto text-sm font-medium text-muted-foreground">{dateLabel}</span>
      </div>

      {/* Day section — one job */}
      <section className="space-y-3">
        <div>
          <h3 className="text-base font-semibold">Sales on this day</h3>
          <p className="text-sm text-muted-foreground">
            {dayStandingLabel(daySummary.day_standing)} · {daySummary.orders_count} order
            {daySummary.orders_count === 1 ? '' : 's'}
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            icon={Receipt}
            label="Day sales"
            value={formatCurrency(daySummary.total_sales)}
            subtext={`${daySummary.orders_count} orders`}
          />
          <SummaryCard
            icon={CheckCircle2}
            label="Paid upfront"
            value={formatCurrency(daySummary.total_paid)}
            tone="success"
            subtext={`${daySummary.paid_orders_count} fully paid`}
          />
          <SummaryCard
            icon={TrendingDown}
            label="Debt taken"
            value={formatCurrency(daySummary.total_debt_incurred)}
            tone={Number(daySummary.total_debt_incurred) > 0 ? 'destructive' : 'default'}
            subtext={`${daySummary.debt_orders_count} on account`}
          />
          <SummaryCard
            icon={Wallet}
            label="Collected on debt"
            value={formatCurrency(daySummary.debt_collected)}
            tone={Number(daySummary.debt_collected) > 0 ? 'success' : 'default'}
            subtext="Settlements this day"
          />
        </div>
      </section>

      {/* Orders for the day */}
      <section className="space-y-3">
        <h3 className="text-base font-semibold">Orders</h3>
        {orders.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="No sales for this customer on this day"
            description="Pick another day, or return to the daily board to review other customers."
            actionLabel="Back to Daily Sales"
            onAction={() => navigate(dailySalesListPath(date))}
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Sale #</DataTableHead>
              <DataTableHead align="right">Total</DataTableHead>
              <DataTableHead align="right">Paid</DataTableHead>
              <DataTableHead align="right">Debt</DataTableHead>
              <DataTableHead>Status</DataTableHead>
              <DataTableHead align="right"> </DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {orders.map((order) => (
                <DataTableRow key={order.id}>
                  <DataTableCell>
                    <button
                      type="button"
                      className="font-medium text-primary hover:underline"
                      onClick={() => openReceipt(order)}
                    >
                      {order.sale_number}
                    </button>
                    <div className="text-xs text-muted-foreground">
                      {order.occurred_at ? formatDateTime(order.occurred_at) : '—'}
                    </div>
                  </DataTableCell>
                  <DataTableCell align="right">{formatCurrency(order.total)}</DataTableCell>
                  <DataTableCell align="right">{formatCurrency(order.paid_amount)}</DataTableCell>
                  <DataTableCell align="right">
                    {Number(order.debt_amount) > 0 ? (
                      <span className="font-semibold text-destructive">
                        {formatCurrency(order.debt_amount)}
                      </span>
                    ) : (
                      '—'
                    )}
                  </DataTableCell>
                  <DataTableCell>
                    {order.payment_status === 'paid' && (
                      <Badge variant="outline" className="border-success/30 bg-success/10 text-success">
                        Paid
                      </Badge>
                    )}
                    {order.payment_status === 'debt' && (
                      <Badge
                        variant="outline"
                        className="border-destructive/30 bg-destructive/10 text-destructive"
                      >
                        Debt
                      </Badge>
                    )}
                    {order.payment_status === 'partial' && (
                      <Badge
                        variant="outline"
                        className="border-amber-500/30 bg-amber-500/10 text-amber-600"
                      >
                        Partial
                      </Badge>
                    )}
                  </DataTableCell>
                  <DataTableCell align="right">
                    <Button variant="ghost" size="sm" onClick={() => openReceipt(order)}>
                      Receipt
                    </Button>
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        )}
      </section>

      {/* Standing / lifetime — separate section so the day view stays calm */}
      <section className="space-y-3 border-t pt-6">
        <div>
          <h3 className="text-base font-semibold">Account overview</h3>
          <p className="text-sm text-muted-foreground">
            Standing across all time — separate from the day above.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SummaryCard
            icon={Wallet}
            label="Wallet debt"
            value={formatCurrency(standing?.wallet_debt || 0)}
            tone={Number(standing?.wallet_debt) > 0 ? 'destructive' : 'default'}
          />
          <SummaryCard
            icon={Receipt}
            label="Lifetime orders"
            value={String(standing?.lifetime_orders || 0)}
          />
          <SummaryCard
            icon={Users}
            label="Lifetime sales"
            value={formatCurrency(standing?.lifetime_sales_total || 0)}
          />
        </div>
      </section>

      <SaleDetailDialog
        sale={selectedSale}
        open={showReceipt}
        onOpenChange={setShowReceipt}
        canRefund={canRefund}
        onRefund={(sale) => {
          setShowReceipt(false);
          setRefundSale(sale);
        }}
        onPrint={() => window.print()}
      />
      <RefundSaleDialog
        sale={refundSale}
        open={Boolean(refundSale)}
        onOpenChange={(open) => !open && setRefundSale(null)}
        onSubmit={handleRefundSubmit}
        submitting={refundSubmitting}
      />
      <ReceiveWalletPaymentDialog
        open={payOpen}
        customer={
          payOpen
            ? {
                id: customer.id,
                name: customer.name,
                phone: customer.phone,
                wallet_balance: customer.wallet_balance,
              }
            : null
        }
        onOpenChange={(open) => !open && setPayOpen(false)}
        onSuccess={() => {
          setPayOpen(false);
          load();
          dispatchNavBadgesRefresh();
        }}
      />
    </PageShell>
  );
}
