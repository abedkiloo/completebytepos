import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ArrowRight,
  Banknote,
  CreditCard,
  Package,
  Receipt,
  ShoppingCart,
  TrendingUp,
  Users,
  Wallet,
} from 'lucide-react';

import { reportsAPI } from '../../services/api';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import {
  reportsEnableSalesReports,
  reportsEnableProductReports,
  reportsEnableInventoryReports,
  reportsEnableInvoiceReports,
  reportsEnableCashReports,
  reportsShowDiscount,
  reportsShowTax,
  reportsShowLegacyCatalog,
} from '../../utils/reportDisplay';
import {
  formatCompactCurrency,
  formatCurrency,
  formatNumber,
} from '../../utils/formatters';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Skeleton } from '../ui/skeleton';

// --------------------------------------------------------------------------
// Period selector primitives
// --------------------------------------------------------------------------

const PERIODS = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'Week' },
  { id: 'month', label: 'Month' },
];

function PeriodPills({ value, onChange }) {
  return (
    <div className="inline-flex items-center rounded-md border bg-muted/30 p-0.5 text-xs">
      {PERIODS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onChange(p.id)}
          className={`rounded px-2.5 py-1 font-medium transition ${
            value === p.id
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------
// Generic card shell — header with icon/title/period + content area
// --------------------------------------------------------------------------

function ReportCard({
  icon: Icon,
  title,
  description,
  period,
  onPeriodChange,
  onOpen,
  openLabel = 'Open full report',
  children,
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
        <div className="flex items-start gap-3">
          {Icon ? (
            <div className="rounded-md bg-primary/10 p-2 text-primary">
              <Icon className="h-5 w-5" />
            </div>
          ) : null}
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </div>
        <PeriodPills value={period} onChange={onPeriodChange} />
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        {children}
        {onOpen ? (
          <button
            type="button"
            onClick={onOpen}
            className="mt-4 inline-flex items-center gap-1 self-start text-xs font-medium text-primary hover:underline"
          >
            {openLabel}
            <ArrowRight className="h-3 w-3" />
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------------
// Small data-display helpers
// --------------------------------------------------------------------------

function Stat({ label, value, sub, tone }) {
  const toneClass =
    tone === 'good'
      ? 'text-emerald-600'
      : tone === 'bad'
      ? 'text-destructive'
      : 'text-foreground';
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={`text-lg font-semibold ${toneClass}`}>{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function EmptyChart({ message = 'No data yet for this period' }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
      {message}
    </div>
  );
}

// Stable, accessible colour palette so charts read well in light + dark.
const CHART_COLOURS = [
  '#2563eb', // blue-600
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#ec4899', // pink-500
  '#8b5cf6', // violet-500
  '#06b6d4', // cyan-500
];

// --------------------------------------------------------------------------
// Hook: load a report endpoint with period support
// --------------------------------------------------------------------------

function useReport(fetcher, period) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetcher({ period });
      setData(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load report');
    } finally {
      setLoading(false);
    }
  }, [fetcher, period]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

function chartHeight(extra = 0) {
  return 160 + extra;
}

// --------------------------------------------------------------------------
// Individual report tiles
// --------------------------------------------------------------------------

function SalesOverviewTile({ onOpen, showDiscount, showTax }) {
  const [period, setPeriod] = useState('today');
  const { data, loading, error } = useReport(reportsAPI.salesOverview, period);

  const summary = data?.summary || {};
  const trend = data?.trend || [];

  return (
    <ReportCard
      icon={TrendingUp}
      title="Sales overview"
      description="Revenue, ticket count and the daily trend."
      period={period}
      onPeriodChange={setPeriod}
      onOpen={onOpen}
    >
      <div className="grid grid-cols-3 gap-3 pb-3">
        {loading ? (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        ) : (
          <>
            <Stat
              label="Revenue"
              value={formatCompactCurrency(summary.gross_revenue || 0)}
              sub={`${formatNumber(summary.sales_count || 0)} sales`}
            />
            <Stat
              label="Avg ticket"
              value={formatCurrency(summary.avg_ticket || 0)}
              sub={`${formatNumber(summary.items_sold || 0)} items`}
            />
            {showDiscount ? (
            <Stat
              label="Discount"
              value={formatCompactCurrency(summary.discount || 0)}
              sub={showTax ? `Tax ${formatCompactCurrency(summary.tax || 0)}` : undefined}
            />
            ) : showTax ? (
            <Stat
              label="Tax"
              value={formatCompactCurrency(summary.tax || 0)}
            />
            ) : null}
          </>
        )}
      </div>
      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyChart message={error} />
      ) : trend.length === 0 ? (
        <EmptyChart />
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight()}>
          <LineChart data={trend} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(d) => (d ? d.slice(5) : '')}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => formatCompactCurrency(v)}
              width={50}
            />
            <Tooltip
              formatter={(value, name) =>
                name === 'revenue'
                  ? [formatCurrency(value), 'Revenue']
                  : [formatNumber(value), 'Sales']
              }
              labelStyle={{ fontSize: 12 }}
              contentStyle={{ fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke={CHART_COLOURS[0]}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ReportCard>
  );
}

function TopProductsTile({ onOpen }) {
  const [period, setPeriod] = useState('week');
  const { data, loading, error } = useReport(reportsAPI.topProducts, period);

  const items = data?.items || [];
  const chartData = useMemo(
    () =>
      items.slice(0, 6).map((row) => ({
        name: row.name?.length > 18 ? `${row.name.slice(0, 18)}…` : row.name,
        quantity: row.quantity_sold,
        revenue: row.revenue,
      })),
    [items]
  );

  return (
    <ReportCard
      icon={ShoppingCart}
      title="Top products"
      description="Best-selling SKUs by quantity moved."
      period={period}
      onPeriodChange={setPeriod}
      onOpen={onOpen}
    >
      {loading ? (
        <Skeleton className="h-52 w-full" />
      ) : error ? (
        <EmptyChart message={error} />
      ) : items.length === 0 ? (
        <EmptyChart message="No sales recorded in this period" />
      ) : (
        <>
          <ResponsiveContainer width="100%" height={chartHeight(30)}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
            >
              <XAxis
                type="number"
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => formatNumber(v)}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 10 }}
                width={120}
              />
              <Tooltip
                formatter={(value, name) =>
                  name === 'revenue'
                    ? [formatCurrency(value), 'Revenue']
                    : [formatNumber(value), 'Units']
                }
                labelStyle={{ fontSize: 12 }}
                contentStyle={{ fontSize: 12 }}
              />
              <Bar dataKey="quantity" fill={CHART_COLOURS[1]} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <ul className="mt-2 space-y-1 text-xs">
            {items.slice(0, 3).map((row) => (
              <li
                key={row.product_id}
                className="flex items-center justify-between border-b border-border/40 py-1 last:border-b-0"
              >
                <span className="truncate text-foreground">{row.name}</span>
                <span className="ml-2 font-medium text-muted-foreground">
                  {formatNumber(row.quantity_sold)} · {formatCompactCurrency(row.revenue)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </ReportCard>
  );
}

function CashAndPaymentsTile({ onOpen }) {
  const [period, setPeriod] = useState('today');
  const { data, loading, error } = useReport(reportsAPI.cashAndPayments, period);

  const summary = data?.summary || {};
  const rows = data?.by_method || [];
  const chartData = useMemo(
    () =>
      rows
        .filter((r) => r.total > 0)
        .map((r) => ({ name: prettyMethod(r.method), value: r.total })),
    [rows]
  );

  return (
    <ReportCard
      icon={Wallet}
      title="Cash & payments"
      description="Money in by payment method."
      period={period}
      onPeriodChange={setPeriod}
      onOpen={onOpen}
    >
      <div className="grid grid-cols-2 gap-3 pb-3">
        {loading ? (
          <>
            <Skeleton className="h-12 w-full" />
          </>
        ) : (
          <>
            <Stat
              label="Total received"
              value={formatCompactCurrency(summary.total_in || 0)}
              sub={`Sales ${formatCompactCurrency(summary.sales_total || 0)}`}
            />
            <Stat
              label="Invoice payments"
              value={formatCompactCurrency(summary.payments_total || 0)}
            />
          </>
        )}
      </div>
      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyChart message={error} />
      ) : chartData.length === 0 ? (
        <EmptyChart />
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight()}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              innerRadius={40}
              outerRadius={70}
              paddingAngle={2}
            >
              {chartData.map((entry, idx) => (
                <Cell
                  key={entry.name}
                  fill={CHART_COLOURS[idx % CHART_COLOURS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [formatCurrency(value), name]}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend
              iconType="circle"
              wrapperStyle={{ fontSize: 11 }}
              align="center"
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ReportCard>
  );
}

function InventoryHealthTile({ onOpen }) {
  const [period, setPeriod] = useState('week');
  const { data, loading, error } = useReport(reportsAPI.inventoryHealth, period);

  const summary = data?.summary || {};
  const atRisk = data?.at_risk || [];

  return (
    <ReportCard
      icon={Package}
      title="Inventory health"
      description="Stock value, low and out-of-stock alerts."
      period={period}
      onPeriodChange={setPeriod}
      onOpen={onOpen}
    >
      <div className="grid grid-cols-3 gap-3 pb-3">
        {loading ? (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        ) : (
          <>
            <Stat
              label="Stock value"
              value={formatCompactCurrency(summary.inventory_value || 0)}
              sub={`${formatNumber(summary.active_products || 0)} active`}
            />
            <Stat
              label="Low stock"
              value={formatNumber(summary.low_stock_count || 0)}
              tone={summary.low_stock_count > 0 ? 'bad' : undefined}
            />
            <Stat
              label="Out of stock"
              value={formatNumber(summary.out_of_stock_count || 0)}
              tone={summary.out_of_stock_count > 0 ? 'bad' : undefined}
            />
          </>
        )}
      </div>
      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyChart message={error} />
      ) : atRisk.length === 0 ? (
        <EmptyChart message="All stock levels look healthy" />
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight()}>
          <BarChart
            data={atRisk.slice(0, 6).map((p) => ({
              name: (p.name || '').slice(0, 16),
              quantity: p.stock_quantity,
              threshold: p.low_stock_threshold,
            }))}
            margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
          >
            <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 10 }} width={30} />
            <Tooltip contentStyle={{ fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="quantity" fill={CHART_COLOURS[2]} name="On hand" />
            <Bar dataKey="threshold" fill={CHART_COLOURS[3]} name="Low-stock at" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ReportCard>
  );
}

function CustomerOutstandingTile({ onOpen }) {
  const [period, setPeriod] = useState('month');
  const { data, loading, error } = useReport(reportsAPI.customerOutstanding, period);

  const summary = data?.summary || {};
  const aging = data?.aging || [];

  return (
    <ReportCard
      icon={Receipt}
      title="Customer outstanding"
      description="Money owed to you, with AR aging."
      period={period}
      onPeriodChange={setPeriod}
      onOpen={onOpen}
    >
      <div className="grid grid-cols-3 gap-3 pb-3">
        {loading ? (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        ) : (
          <>
            <Stat
              label="Total owed"
              value={formatCompactCurrency(summary.total_outstanding || 0)}
              tone={summary.total_outstanding > 0 ? 'bad' : 'good'}
              sub={`${formatNumber(summary.invoice_count || 0)} invoices`}
            />
            <Stat
              label="Overdue"
              value={formatNumber(summary.overdue_count || 0)}
              tone={summary.overdue_count > 0 ? 'bad' : undefined}
            />
            <Stat
              label="New this period"
              value={formatNumber(summary.new_invoices_in_period || 0)}
            />
          </>
        )}
      </div>
      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyChart message={error} />
      ) : aging.length === 0 ? (
        <EmptyChart message="No outstanding invoices" />
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight()}>
          <BarChart data={aging} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
            <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => formatCompactCurrency(v)} width={50} />
            <Tooltip
              formatter={(v) => [formatCurrency(v), 'Outstanding']}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
              {aging.map((row, idx) => (
                <Cell
                  key={row.bucket}
                  fill={
                    // Older buckets shaded redder.
                    idx === 0
                      ? CHART_COLOURS[1]
                      : idx === 1
                      ? CHART_COLOURS[2]
                      : idx === 2
                      ? '#f97316'
                      : '#dc2626'
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </ReportCard>
  );
}

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

function prettyMethod(method) {
  if (!method) return 'Unknown';
  return method
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// --------------------------------------------------------------------------
// Top-level page layout
// --------------------------------------------------------------------------

export default function ReportsHub() {
  const navigate = useNavigate();
  const { settings: reportSettings } = useModuleSettings('reports');
  const goLegacy = (reportName) => () => navigate(`/reports?report=${reportName}`);

  const showSales = reportsEnableSalesReports(reportSettings);
  const showProducts = reportsEnableProductReports(reportSettings);
  const showCash = reportsEnableCashReports(reportSettings);
  const showInventory = reportsEnableInventoryReports(reportSettings);
  const showInvoice = reportsEnableInvoiceReports(reportSettings);
  const showDiscount = reportsShowDiscount(reportSettings);
  const showTax = reportsShowTax(reportSettings);
  const showLegacy = reportsShowLegacyCatalog(reportSettings);

  const visibleCount = [showSales, showProducts, showCash, showInventory, showInvoice].filter(Boolean).length;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
          <p className="text-sm text-muted-foreground">
            Daily, weekly and monthly view of the metrics that matter most for the
            store.
          </p>
          {showLegacy ? (
            <button
              type="button"
              onClick={() => navigate('/reports?report=__legacy__')}
              className="mt-2 text-xs font-medium text-primary hover:underline"
            >
              Browse all report types
            </button>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Banknote className="h-3.5 w-3.5" /> Sales
          </span>
          <span className="inline-flex items-center gap-1">
            <Users className="h-3.5 w-3.5" /> Customers
          </span>
          <span className="inline-flex items-center gap-1">
            <CreditCard className="h-3.5 w-3.5" /> Payments
          </span>
        </div>
      </header>

      {visibleCount === 0 ? (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          All report tiles are turned off in System Settings → Reports &amp; analytics.
        </div>
      ) : (
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-2">
        {showSales ? (
          <>
            <SalesOverviewTile onOpen={goLegacy('sales')} showDiscount={showDiscount} showTax={showTax} />
            <Card className="flex flex-col border-dashed">
              <CardHeader className="pb-3">
                <div className="flex items-start gap-3">
                  <div className="rounded-md bg-primary/10 p-2 text-primary">
                    <Users className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-base">Sales by staff</CardTitle>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Month-end performance per person — download CSV to share for rewards or commission proof.
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="mt-auto pt-0">
                <button
                  type="button"
                  onClick={() => navigate('/reports?report=sales-by-person')}
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  Open staff report
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </CardContent>
            </Card>
          </>
        ) : null}
        {showProducts ? <TopProductsTile onOpen={goLegacy('products')} /> : null}
        {showCash ? <CashAndPaymentsTile onOpen={goLegacy('income')} /> : null}
        {showInventory ? <InventoryHealthTile onOpen={goLegacy('inventory')} /> : null}
        {showInvoice ? <CustomerOutstandingTile onOpen={goLegacy('invoice')} /> : null}
      </div>
      )}
    </div>
  );
}
