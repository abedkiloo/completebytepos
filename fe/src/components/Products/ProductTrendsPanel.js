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
const QUARTER_SPANS = [4, 6, 8];
const CHART_COLOURS = CHART_SERIES;
const INSIGHT_TONE = {
  reorder: 'border-emerald-300/70 bg-emerald-50/80 text-emerald-950',
  rising: 'border-emerald-300/70 bg-emerald-50/80 text-emerald-950',
  overstock: 'border-amber-300/70 bg-amber-50/80 text-amber-950',
  falling: 'border-amber-300/70 bg-amber-50/80 text-amber-950',
  peak: 'border-sky-300/70 bg-sky-50/80 text-sky-950',
  compare_leader: 'border-violet-300/70 bg-violet-50/80 text-violet-950',
};

function currentEndDefaults() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const quarter = Math.floor((month - 1) / 3) + 1;
  return { year, month, quarter };
}

/**
 * Month or quarter performance charts for one product, with variant / peer compare.
 *
 * Works for any product opened from the catalogue — not only top sellers.
 * Supports an explicit end month/quarter (not only “through today”) and optional
 * multi-product compare lines for purchase decisions.
 *
 * @param {object} props
 * @param {number|string} props.productId Positive product id.
 * @param {number|string|null} [props.variantId] Initial focused variant id.
 * @param {Array<object>} [props.variants] Product variant rows for the picker.
 * @param {function} [props.onVariantChange] Called when the scope picker changes.
 * @param {Array<number|string>} [props.compareProductIds] Peer product ids (max 4).
 */
export default function ProductTrendsPanel({
  productId,
  variantId = null,
  variants = [],
  onVariantChange,
  compareProductIds = [],
}) {
  const defaults = currentEndDefaults();
  const [grain, setGrain] = useState('month');
  const [span, setSpan] = useState(12);
  const [endYear, setEndYear] = useState(defaults.year);
  const [endMonth, setEndMonth] = useState(defaults.month);
  const [endQuarter, setEndQuarter] = useState(defaults.quarter);
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

  const endParam = useMemo(() => {
    if (grain === 'quarter') {
      return `${endYear}-Q${endQuarter}`;
    }
    return `${endYear}-${String(endMonth).padStart(2, '0')}`;
  }, [grain, endYear, endMonth, endQuarter]);

  const compareParam = useMemo(() => {
    const ids = (compareProductIds || [])
      .map((id) => Number(id))
      .filter((id) => Number.isFinite(id) && id > 0 && id !== Number(productId));
    return ids.slice(0, 4).join(',');
  }, [compareProductIds, productId]);

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError('');
    try {
      const params = {
        product_id: productId,
        grain,
        end: endParam,
        include_variants: scopeVariantId ? '0' : '1',
      };
      if (grain === 'quarter') {
        params.quarters = span;
      } else {
        params.months = span;
      }
      if (scopeVariantId) params.variant_id = scopeVariantId;
      if (compareParam) params.compare_ids = compareParam;
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
  }, [productId, scopeVariantId, grain, span, endParam, compareParam]);

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
  const compareKeys = useMemo(() => data?.compare_keys || [], [data]);
  const compareSeries = useMemo(() => data?.compare_series || [], [data]);
  const compareTotals = useMemo(() => data?.compare_totals || [], [data]);
  const insights = useMemo(() => data?.insights || [], [data]);
  const summary = data?.summary || {};
  const periodWord = grain === 'quarter' ? 'quarter' : 'month';
  const hasVariantPicker = Array.isArray(variants) && variants.length > 0;
  const yearOptions = useMemo(() => {
    const y = defaults.year;
    return [y, y - 1, y - 2, y - 3, y - 4];
  }, [defaults.year]);

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
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Ending
            <select
              aria-label="Trend end year"
              data-testid="product-trends-end-year"
              className="h-8 rounded-md border border-input bg-background px-2 text-foreground"
              value={endYear}
              onChange={(e) => setEndYear(Number(e.target.value) || defaults.year)}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            {grain === 'quarter' ? (
              <select
                aria-label="Trend end quarter"
                data-testid="product-trends-end-quarter"
                className="h-8 rounded-md border border-input bg-background px-2 text-foreground"
                value={endQuarter}
                onChange={(e) => setEndQuarter(Number(e.target.value) || 1)}
              >
                {[1, 2, 3, 4].map((q) => (
                  <option key={q} value={q}>
                    Q{q}
                  </option>
                ))}
              </select>
            ) : (
              <select
                aria-label="Trend end month"
                data-testid="product-trends-end-month"
                className="h-8 rounded-md border border-input bg-background px-2 text-foreground"
                value={endMonth}
                onChange={(e) => setEndMonth(Number(e.target.value) || 1)}
              >
                {[
                  'Jan',
                  'Feb',
                  'Mar',
                  'Apr',
                  'May',
                  'Jun',
                  'Jul',
                  'Aug',
                  'Sep',
                  'Oct',
                  'Nov',
                  'Dec',
                ].map((label, idx) => (
                  <option key={label} value={idx + 1}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </label>
        </div>
      </div>
      {data?.end_period_label ? (
        <p className="text-xs text-muted-foreground" data-testid="product-trends-end-label">
          Window ends {data.end_period_label}
          {compareParam ? ' · multi-product compare on' : ''}.
        </p>
      ) : null}

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

          {insights.length > 0 ? (
            <div
              className="space-y-2 rounded-md border border-border/70 bg-muted/15 p-3"
              data-testid="product-trends-insights"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
                Purchase cues
              </p>
              <ul className="space-y-2">
                {insights.map((tip, idx) => (
                  <li
                    key={`${tip.severity}-${idx}`}
                    className={cn(
                      'rounded-md border px-3 py-2 text-sm',
                      INSIGHT_TONE[tip.severity] ||
                        'border-border bg-background text-foreground'
                    )}
                  >
                    <p className="font-medium">{tip.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed opacity-90">
                      {tip.detail}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {compareSeries.length > 0 && compareKeys.length > 1 ? (
            <>
              <ChartCard
                title={`Product compare — units by ${periodWord}`}
                testId="product-trends-compare-chart"
              >
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart
                    data={compareSeries}
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
                        const meta = compareKeys.find((k) => k.key === name);
                        return [formatNumber(value), meta?.label || name];
                      }}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {compareKeys.map((key, index) => (
                      <Line
                        key={key.key}
                        type="monotone"
                        dataKey={key.key}
                        name={key.label}
                        stroke={CHART_COLOURS[index % CHART_COLOURS.length]}
                        strokeWidth={key.is_primary ? 3 : 2}
                        strokeDasharray={key.is_primary ? undefined : '4 3'}
                        dot={{ r: 2 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
              {compareTotals.length > 0 ? (
                <ChartCard
                  title="Which product sold more (this window)"
                  testId="product-trends-compare-totals"
                >
                  <ResponsiveContainer
                    width="100%"
                    height={Math.max(140, compareTotals.length * 32)}
                  >
                    <BarChart
                      data={compareTotals}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 4, bottom: 0 }}
                    >
                      <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                      <YAxis
                        type="category"
                        dataKey="label"
                        width={120}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip
                        formatter={(value) => [formatNumber(value), 'Units']}
                        contentStyle={{ fontSize: 12 }}
                      />
                      <Bar
                        dataKey="quantity_sold"
                        fill={CHART_COLOURS[0]}
                        radius={[0, 3, 3, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              ) : null}
            </>
          ) : null}

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
