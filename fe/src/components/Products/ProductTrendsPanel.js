import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
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

import { reportsAPI } from '../../services/api';
import {
  formatCompactCurrency,
  formatCurrency,
  formatNumber,
} from '../../utils/formatters';
import { Skeleton } from '../ui/skeleton';
import { cn } from '../../lib/cn';

const MONTH_OPTIONS = [6, 12, 18, 24];
const CHART_COLOURS = ['#2563eb', '#f59e0b', '#10b981', '#06b6d4', '#64748b', '#ec4899'];

/**
 * Month-over-month sales and receiving charts for one product.
 *
 * @param {object} props
 * @param {number|string} props.productId Positive product id.
 * @param {number|string|null} [props.variantId] Optional variant filter.
 */
export default function ProductTrendsPanel({ productId, variantId = null }) {
  const [months, setMonths] = useState(12);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError('');
    try {
      const params = { product_id: productId, months };
      if (variantId) params.variant_id = variantId;
      const res = await reportsAPI.productTrends(params);
      setData(res.data);
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'Could not load product trends.';
      setError(typeof msg === 'string' ? msg : 'Could not load product trends.');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [productId, variantId, months]);

  useEffect(() => {
    load();
  }, [load]);

  const series = useMemo(() => {
    const rows = data?.months || [];
    return rows.map((row) => ({
      ...row,
      shortLabel: (row.label || '').split(' ')[0] || row.month,
      revenueNum: Number(row.revenue) || 0,
    }));
  }, [data]);

  const channelData = useMemo(() => {
    const rows = data?.channels || [];
    return rows
      .filter((row) => (row.quantity || 0) > 0)
      .map((row) => ({
        name: row.channel,
        value: row.quantity,
      }));
  }, [data]);

  const summary = data?.summary || {};

  return (
    <div className="space-y-5" data-testid="product-trends-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Performance</h3>
          <p className="text-xs text-muted-foreground">
            Units sold, revenue, and stock received by month
            {variantId ? ' for this variant' : ''}.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          Months
          <select
            aria-label="Trend months"
            data-testid="product-trends-months"
            className="h-8 rounded-md border border-input bg-background px-2 text-foreground"
            value={months}
            onChange={(e) => setMonths(Number(e.target.value) || 12)}
          >
            {MONTH_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-destructive" data-testid="product-trends-error">
          {error}
        </p>
      ) : (
        <>
          <div
            className="grid grid-cols-2 gap-2 sm:grid-cols-4"
            data-testid="product-trends-summary"
          >
            <SummaryTile
              label="Units sold"
              value={formatNumber(summary.quantity_sold || 0)}
            />
            <SummaryTile
              label="Revenue"
              value={formatCompactCurrency(summary.revenue || 0)}
            />
            <SummaryTile
              label="Avg / month"
              value={formatNumber(summary.avg_monthly_quantity || 0)}
            />
            <SummaryTile
              label="Best month"
              value={summary.best_month_label || '—'}
            />
          </div>

          <ChartCard title="Units sold over months" testId="product-trends-sold-chart">
            {series.every((row) => row.quantity_sold === 0) ? (
              <EmptyChart message="No sales in this window" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="shortLabel" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} width={40} allowDecimals={false} />
                  <Tooltip
                    formatter={(value, name) =>
                      name === 'revenueNum'
                        ? [formatCurrency(value), 'Revenue']
                        : [formatNumber(value), name === 'order_count' ? 'Orders' : 'Units']
                    }
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.label || ''}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="quantity_sold"
                    name="Units"
                    stroke={CHART_COLOURS[0]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard
            title="Sold vs received"
            testId="product-trends-sold-received-chart"
          >
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="shortLabel" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} width={40} allowDecimals={false} />
                <Tooltip
                  formatter={(value, name) => [
                    formatNumber(value),
                    name === 'quantity_sold' ? 'Sold' : 'Received',
                  ]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.label || ''}
                  contentStyle={{ fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar
                  dataKey="quantity_sold"
                  name="Sold"
                  fill={CHART_COLOURS[0]}
                  radius={[3, 3, 0, 0]}
                />
                <Bar
                  dataKey="quantity_received"
                  name="Received"
                  fill={CHART_COLOURS[1]}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Revenue by month" testId="product-trends-revenue-chart">
            {series.every((row) => row.revenueNum === 0) ? (
              <EmptyChart message="No revenue in this window" />
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={series} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                  <XAxis dataKey="shortLabel" tick={{ fontSize: 10 }} />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    width={48}
                    tickFormatter={(v) => formatCompactCurrency(v)}
                  />
                  <Tooltip
                    formatter={(value) => [formatCurrency(value), 'Revenue']}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.label || ''}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Bar dataKey="revenueNum" fill={CHART_COLOURS[0]} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          {channelData.length > 0 ? (
            <ChartCard title="Sales by channel" testId="product-trends-channel-chart">
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={channelData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={70}
                    paddingAngle={2}
                  >
                    {channelData.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={CHART_COLOURS[index % CHART_COLOURS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value, name) => [formatNumber(value), name]}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
          ) : null}
        </>
      )}
    </div>
  );
}

function SummaryTile({ label, value }) {
  return (
    <div className="rounded-md border border-border/60 bg-muted/20 px-3 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 truncate text-sm font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

function ChartCard({ title, testId, children }) {
  return (
    <div
      className={cn('rounded-md border border-border/60 bg-background p-3')}
      data-testid={testId}
    >
      <p className="mb-2 text-xs font-medium text-foreground">{title}</p>
      {children}
    </div>
  );
}

function EmptyChart({ message = 'No data' }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
      {message}
    </div>
  );
}
