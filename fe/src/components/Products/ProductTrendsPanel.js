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
import { variantDisplayLabel } from '../../utils/variantCombinations';
import { CHART_SERIES } from '../../utils/chartTheme';
import { Skeleton } from '../ui/skeleton';
import { cn } from '../../lib/cn';

const MONTH_SPANS = [6, 12, 18, 24];
const QUARTER_SPANS = [4, 8];
const CHART_COLOURS = CHART_SERIES;

/**
 * Month or quarter performance charts for one product, with variant compare.
 *
 * Works for any product opened from the catalogue — not only top sellers.
 *
 * @param {object} props
 * @param {number|string} props.productId Positive product id.
 * @param {number|string|null} [props.variantId] Initial focused variant id.
 * @param {Array<object>} [props.variants] Product variant rows for the picker.
 * @param {function} [props.onVariantChange] Called when the scope picker changes.
 */
export default function ProductTrendsPanel({
  productId,
  variantId = null,
  variants = [],
  onVariantChange,
}) {
  const [grain, setGrain] = useState('month');
  const [span, setSpan] = useState(12);
  const [scopeVariantId, setScopeVariantId] = useState(variantId);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setScopeVariantId(variantId);
  }, [variantId, productId]);

  useEffect(() => {
    setSpan(grain === 'quarter' ? 4 : 12);
  }, [grain]);

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError('');
    try {
      const params = {
        product_id: productId,
        grain,
        include_variants: scopeVariantId ? '0' : '1',
      };
      if (grain === 'quarter') {
        params.quarters = span;
      } else {
        params.months = span;
      }
      if (scopeVariantId) params.variant_id = scopeVariantId;
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
  }, [productId, scopeVariantId, grain, span]);

  useEffect(() => {
    load();
  }, [load]);

  const series = useMemo(() => {
    const rows = data?.periods || data?.months || [];
    return rows.map((row) => ({
      ...row,
      shortLabel:
        grain === 'quarter'
          ? row.label || row.period
          : (row.label || '').split(' ')[0] || row.period || row.month,
      revenueNum: Number(row.revenue) || 0,
    }));
  }, [data, grain]);

  const channelData = useMemo(() => {
    const rows = data?.channels || [];
    return rows
      .filter((row) => (row.quantity || 0) > 0)
      .map((row) => ({
        name: row.channel,
        value: row.quantity,
      }));
  }, [data]);

  const variantTotals = useMemo(() => data?.variants || [], [data]);
  const variantKeys = useMemo(() => data?.variant_keys || [], [data]);
  const variantSeries = useMemo(() => data?.variant_series || [], [data]);
  const summary = data?.summary || {};
  const periodWord = grain === 'quarter' ? 'quarter' : 'month';
  const hasVariantPicker = Array.isArray(variants) && variants.length > 0;

  const handleScopeChange = (nextId) => {
    const value = nextId === '' || nextId == null ? null : nextId;
    setScopeVariantId(value);
    if (typeof onVariantChange === 'function') {
      onVariantChange(value);
    }
  };

  return (
    <div className="space-y-5" data-testid="product-trends-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Performance</h3>
          <p className="text-xs text-muted-foreground">
            Any catalogue product — units sold, revenue, and stock received by{' '}
            {periodWord}
            {scopeVariantId ? ' for the selected variant' : ''}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="inline-flex rounded-md border border-input p-0.5"
            role="group"
            aria-label="Trend period type"
          >
            <GrainButton
              active={grain === 'month'}
              onClick={() => setGrain('month')}
              testId="product-trends-grain-month"
            >
              Month
            </GrainButton>
            <GrainButton
              active={grain === 'quarter'}
              onClick={() => setGrain('quarter')}
              testId="product-trends-grain-quarter"
            >
              Quarter
            </GrainButton>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            {grain === 'quarter' ? 'Quarters' : 'Months'}
            <select
              aria-label={grain === 'quarter' ? 'Trend quarters' : 'Trend months'}
              data-testid="product-trends-span"
              className="h-8 rounded-md border border-input bg-background px-2 text-foreground"
              value={span}
              onChange={(e) => setSpan(Number(e.target.value) || (grain === 'quarter' ? 4 : 12))}
            >
              {(grain === 'quarter' ? QUARTER_SPANS : MONTH_SPANS).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {hasVariantPicker ? (
        <label className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          Scope
          <select
            aria-label="Variant performance scope"
            data-testid="product-trends-variant-scope"
            className="h-8 min-w-[12rem] rounded-md border border-input bg-background px-2 text-foreground"
            value={scopeVariantId == null ? '' : String(scopeVariantId)}
            onChange={(e) => handleScopeChange(e.target.value || null)}
          >
            <option value="">All variants (compare)</option>
            {variants.map((variant) => (
              <option key={variant.id} value={String(variant.id)}>
                {variantDisplayLabel(variant)}
                {variant.sku ? ` · ${variant.sku}` : ''}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {/* Keep legacy test id for months select compatibility */}
      <span className="sr-only" data-testid="product-trends-months">
        {grain === 'month' ? span : ''}
      </span>

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
              label={`Avg / ${periodWord}`}
              value={formatNumber(summary.avg_period_quantity ?? summary.avg_monthly_quantity ?? 0)}
            />
            <SummaryTile
              label={`Best ${periodWord}`}
              value={
                summary.best_period_label ||
                summary.best_month_label ||
                '—'
              }
            />
          </div>

          {!scopeVariantId && variantTotals.length > 0 ? (
            <>
              <ChartCard
                title="Variant comparison (units sold)"
                testId="product-trends-variant-compare-chart"
              >
                <ResponsiveContainer width="100%" height={Math.max(160, variantTotals.length * 28)}>
                  <BarChart
                    data={variantTotals}
                    layout="vertical"
                    margin={{ top: 4, right: 16, left: 4, bottom: 0 }}
                  >
                    <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={110}
                      tick={{ fontSize: 10 }}
                    />
                    <Tooltip
                      formatter={(value, name) =>
                        name === 'revenue'
                          ? [formatCurrency(value), 'Revenue']
                          : [formatNumber(value), 'Units']
                      }
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Bar dataKey="quantity_sold" fill={CHART_COLOURS[0]} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <ul
                  className="mt-2 space-y-1 text-xs"
                  data-testid="product-trends-variant-table"
                >
                  {variantTotals.map((row) => (
                    <li
                      key={row.variant_id}
                      className="flex items-center justify-between gap-2 border-b border-border/40 py-1 last:border-0"
                    >
                      <button
                        type="button"
                        className="truncate text-left text-primary underline-offset-2 hover:underline"
                        onClick={() => handleScopeChange(row.variant_id)}
                      >
                        {row.label}
                      </button>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {formatNumber(row.quantity_sold)} ·{' '}
                        {formatCompactCurrency(row.revenue)}
                      </span>
                    </li>
                  ))}
                </ul>
              </ChartCard>

              {variantSeries.length > 0 && variantKeys.length > 0 ? (
                <ChartCard
                  title={`Variant trend by ${periodWord}`}
                  testId="product-trends-variant-trend-chart"
                >
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart
                      data={variantSeries}
                      margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="label"
                        tick={{ fontSize: 10 }}
                        tickFormatter={(label) =>
                          grain === 'quarter'
                            ? label
                            : String(label || '').split(' ')[0]
                        }
                      />
                      <YAxis tick={{ fontSize: 10 }} width={40} allowDecimals={false} />
                      <Tooltip
                        formatter={(value, name) => {
                          const meta = variantKeys.find((k) => k.key === name);
                          return [formatNumber(value), meta?.label || name];
                        }}
                        contentStyle={{ fontSize: 12 }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {variantKeys.map((key, index) => (
                        <Line
                          key={key.key}
                          type="monotone"
                          dataKey={key.key}
                          name={key.label}
                          stroke={CHART_COLOURS[index % CHART_COLOURS.length]}
                          strokeWidth={2}
                          dot={{ r: 2 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </ChartCard>
              ) : null}
            </>
          ) : null}

          <ChartCard
            title={`Units sold over ${periodWord}s`}
            testId="product-trends-sold-chart"
          >
            {series.every((row) => row.quantity_sold === 0) ? (
              <EmptyChart message="No sales in this window" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={series} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="shortLabel" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} width={40} allowDecimals={false} />
                  <Tooltip
                    formatter={(value) => [formatNumber(value), 'Units']}
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

          <ChartCard
            title={`Revenue by ${periodWord}`}
            testId="product-trends-revenue-chart"
          >
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

function GrainButton({ active, onClick, children, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      className={cn(
        'rounded px-2.5 py-1 text-xs font-medium transition-colors',
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground'
      )}
      onClick={onClick}
    >
      {children}
    </button>
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
