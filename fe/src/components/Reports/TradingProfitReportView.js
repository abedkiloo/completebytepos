import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingDown, TrendingUp } from 'lucide-react';
import { cn } from '../../lib/cn';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import {
  DEFAULT_REPORT_PERIOD,
  formatDateForApi,
  periodToDateFilters,
} from '../../utils/reportPeriods';
import { PageShell, PageHeader, PageLoading, EmptyState, FilterBar, FilterField } from '../page';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import PeriodPills from './PeriodPills';

const PROFIT_PERIODS = [
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'year', label: 'This year' },
];

function isoDateOnly(value) {
  if (!value) return '';
  const s = String(value);
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '';
  return formatDateForApi(d);
}

function expensesHrefForRange(dateFrom, dateTo) {
  const from = isoDateOnly(dateFrom);
  const to = isoDateOnly(dateTo);
  if (!from || !to) return null;
  const params = new URLSearchParams({
    date_from: from,
    date_to: to,
    status: 'approved',
    include_in_trading_profit: 'true',
  });
  return `/expenses?${params.toString()}`;
}

function Row({
  label,
  value,
  emphasize = false,
  muted = false,
  to = null,
  onClick = null,
}) {
  const valueClass = emphasize
    ? 'text-base font-semibold tabular-nums'
    : 'text-sm font-medium tabular-nums';
  const labelNode = to ? (
    <Link
      to={to}
      className={cn(
        'text-sm font-medium text-primary underline-offset-2 hover:underline',
        muted && 'text-primary/80'
      )}
    >
      {label}
    </Link>
  ) : onClick ? (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'text-left text-sm font-medium text-primary underline-offset-2 hover:underline',
        muted && 'text-primary/80'
      )}
    >
      {label}
    </button>
  ) : (
    <span className={muted ? 'text-sm text-muted-foreground' : 'text-sm'}>{label}</span>
  );

  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/60 py-2 last:border-0">
      {labelNode}
      {to ? (
        <Link to={to} className={cn(valueClass, 'text-primary hover:underline')}>
          {formatCurrency(value)}
        </Link>
      ) : onClick ? (
        <button
          type="button"
          onClick={onClick}
          className={cn(valueClass, 'text-primary hover:underline')}
        >
          {formatCurrency(value)}
        </button>
      ) : (
        <span className={valueClass}>{formatCurrency(value)}</span>
      )}
    </div>
  );
}

function BreakdownDialog({ open, onOpenChange, loading, error, data }) {
  const cogs = data?.cogs;
  const components = data?.components || [];
  const rows = data?.rows || [];
  const cogsSales = cogs?.sales || [];
  const cogsRefunds = cogs?.refunds || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{data?.title || 'How this was calculated'}</DialogTitle>
          <DialogDescription>
            {data?.formula
              ? `${data.formula}${data.explanation ? ` — ${data.explanation}` : ''}`
              : data?.explanation || 'Breakdown for this trading-profit line.'}
          </DialogDescription>
        </DialogHeader>
        {loading ? <PageLoading rows={4} /> : null}
        {!loading && error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}
        {!loading && !error && data ? (
          <div className="space-y-4 text-sm">
            <div className="flex items-baseline justify-between gap-3 rounded-md border bg-muted/30 px-3 py-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                Total
              </span>
              <span className="text-lg font-semibold tabular-nums">
                {formatCurrency(data.total)}
              </span>
            </div>

            {components.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Calculation
                </p>
                <ul className="space-y-1 rounded-md border px-3 py-2">
                  {components.map((step) => (
                    <li
                      key={`${step.op}-${step.label}`}
                      className="flex items-baseline justify-between gap-3"
                    >
                      <span className="text-muted-foreground">
                        {step.op ? `${step.op} ` : ''}
                        {step.label}
                      </span>
                      <span className="tabular-nums font-medium">
                        {formatCurrency(step.value)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {cogs ? (
              <>
                {cogs.cost_missing_sale_count > 0 ? (
                  <p
                    className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100"
                    role="status"
                  >
                    {cogs.cost_missing_sale_count} sale(s) still have cost concerns.
                    Every tracked product must have a cost on the product or its sizes.
                  </p>
                ) : null}
                {cogs.truncated ? (
                  <p className="text-xs text-warning">
                    Showing {cogs.sales_shown} of {cogs.sale_count} sales.
                  </p>
                ) : null}
                <ul className="space-y-3">
                  {cogsSales.map((sale) => (
                    <li
                      key={sale.sale_id}
                      className="rounded-md border px-3 py-2"
                      data-testid={`cogs-sale-${sale.sale_id}`}
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="font-medium">{sale.sale_number}</span>
                        <span className="tabular-nums text-muted-foreground">
                          Sale {formatCurrency(sale.sale_total)} · COGS{' '}
                          {formatCurrency(sale.cogs)}
                        </span>
                      </div>
                      {(sale.concerns || []).length > 0 ? (
                        <ul className="mt-1 space-y-0.5 text-xs text-amber-800 dark:text-amber-200">
                          {sale.concerns.map((msg) => (
                            <li key={msg}>⚠ {msg}</li>
                          ))}
                        </ul>
                      ) : null}
                      <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                        {(sale.lines || []).map((line, idx) => (
                          <li
                            key={`${sale.sale_id}-${idx}`}
                            className={`flex justify-between gap-2 ${line.cost_missing ? 'text-amber-800 dark:text-amber-200' : ''}`}
                          >
                            <span>
                              {line.product_name}
                              {line.quantity != null ? ` × ${line.quantity}` : ''}
                              {line.unit_cost != null
                                ? ` @ ${formatCurrency(line.unit_cost)}`
                                : ''}
                              {line.cost_missing ? ' · cost missing' : ''}
                            </span>
                            <span className="tabular-nums">
                              {formatCurrency(line.line_cogs)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
                {cogsRefunds.length > 0 ? (
                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Refunds restoring cost
                    </p>
                    <ul className="space-y-2">
                      {cogsRefunds.map((refund) => (
                        <li
                          key={refund.refund_id}
                          className="rounded-md border border-dashed px-3 py-2 text-xs"
                        >
                          <div className="flex justify-between gap-2">
                            <span>Refund on {refund.sale_number || 'sale'}</span>
                            <span className="tabular-nums">
                              −{formatCurrency(refund.cogs_restored)}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : null}

            {!cogs && rows.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Items ({data.rows_shown}
                  {data.truncated ? ` of ${data.row_count}` : ''})
                </p>
                {data.truncated ? (
                  <p className="mb-2 text-xs text-warning">
                    Showing first {data.rows_shown} of {data.row_count}.
                  </p>
                ) : null}
                <ul className="space-y-3">
                  {rows.map((row) => (
                    <li
                      key={row.id}
                      className="rounded-md border px-3 py-2"
                      data-testid={`tp-row-${data.metric}-${row.id}`}
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <div>
                          <p className="font-medium">{row.label}</p>
                          {row.sublabel ? (
                            <p className="text-xs text-muted-foreground">{row.sublabel}</p>
                          ) : null}
                        </div>
                        <span className="tabular-nums font-medium">
                          {formatCurrency(row.amount)}
                        </span>
                      </div>
                      {(row.lines || []).length > 0 ? (
                        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                          {row.lines.map((line, idx) => (
                            <li
                              key={`${row.id}-${idx}`}
                              className="flex justify-between gap-2"
                            >
                              <span>
                                {line.product_name}
                                {line.quantity != null ? ` × ${line.quantity}` : ''}
                                {line.unit_price != null
                                  ? ` @ ${formatCurrency(line.unit_price)}`
                                  : ''}
                              </span>
                              <span className="tabular-nums">
                                {formatCurrency(line.line_total)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {!cogs && rows.length === 0 && components.length === 0 ? (
              <p className="text-sm text-muted-foreground">No contributing items in this period.</p>
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

export default function TradingProfitReportView() {
  const navigate = useNavigate();
  const initialPeriod = PROFIT_PERIODS.some((p) => p.id === DEFAULT_REPORT_PERIOD)
    ? DEFAULT_REPORT_PERIOD
    : 'month';
  const [period, setPeriod] = useState(initialPeriod);
  const [dateFrom, setDateFrom] = useState(
    () => periodToDateFilters(initialPeriod).date_from
  );
  const [dateTo, setDateTo] = useState(() => periodToDateFilters(initialPeriod).date_to);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [drillOpen, setDrillOpen] = useState(false);
  const [drillLoading, setDrillLoading] = useState(false);
  const [drillError, setDrillError] = useState('');
  const [drillData, setDrillData] = useState(null);

  const reportParams = useMemo(
    () =>
      period === 'custom'
        ? { date_from: dateFrom, date_to: dateTo }
        : { period },
    [period, dateFrom, dateTo]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await reportsAPI.tradingProfit(reportParams);
      setData(res.data);
      const from = isoDateOnly(res.data?.date_from);
      const to = isoDateOnly(res.data?.date_to);
      if (from) setDateFrom(from);
      if (to) setDateTo(to);
    } catch (err) {
      setData(null);
      const status = err?.response?.status;
      setError(
        status === 403
          ? 'You do not have permission to view trading profit. Ask an admin to grant Reports → Profit on your role.'
          : err?.response?.data?.error || 'Could not load trading profit.'
      );
    } finally {
      setLoading(false);
    }
  }, [reportParams]);

  useEffect(() => {
    if (period === 'custom') return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const openBreakdown = async (metric) => {
    setDrillOpen(true);
    setDrillLoading(true);
    setDrillError('');
    setDrillData(null);
    try {
      const params =
        period === 'custom'
          ? { date_from: dateFrom, date_to: dateTo, metric }
          : { period, metric };
      const res = await reportsAPI.tradingProfitBreakdown(params);
      setDrillData(res.data);
    } catch (err) {
      setDrillData(null);
      const detail = err?.response?.data?.error;
      setDrillError(
        typeof detail === 'string'
          ? detail
          : detail?.metric?.[0] || 'Could not load breakdown.'
      );
    } finally {
      setDrillLoading(false);
    }
  };

  const applyCustomRange = () => {
    if (!dateFrom || !dateTo) {
      setError('Pick both From and To dates.');
      return;
    }
    if (dateFrom > dateTo) {
      setError('“From” must be on or before “To”.');
      return;
    }
    if (period !== 'custom') {
      setPeriod('custom');
    }
    setLoading(true);
    setError('');
    reportsAPI
      .tradingProfit({ date_from: dateFrom, date_to: dateTo })
      .then((res) => {
        setData(res.data);
        setPeriod('custom');
        const from = isoDateOnly(res.data?.date_from);
        const to = isoDateOnly(res.data?.date_to);
        if (from) setDateFrom(from);
        if (to) setDateTo(to);
      })
      .catch((err) => {
        setData(null);
        const status = err?.response?.status;
        setError(
          status === 403
            ? 'You do not have permission to view trading profit. Ask an admin to grant Reports → Profit on your role.'
            : err?.response?.data?.error || 'Could not load trading profit.'
        );
      })
      .finally(() => setLoading(false));
  };

  const onPresetChange = (next) => {
    const filters = periodToDateFilters(next);
    setDateFrom(filters.date_from);
    setDateTo(filters.date_to);
    setPeriod(next);
  };

  const summary = data?.summary;
  const isLoss = summary != null && Number(summary.net_profit) < 0;
  const isCashLoss = summary != null && Number(summary.cash_net_profit) < 0;
  const TrendIcon = isLoss ? TrendingDown : TrendingUp;
  const CashTrendIcon = isCashLoss ? TrendingDown : TrendingUp;
  const rangeLabel =
    period === 'custom'
      ? `${dateFrom || '…'} → ${dateTo || '…'}`
      : `${data?.period || period}${dateFrom && dateTo ? ` · ${dateFrom} → ${dateTo}` : ''}`;
  const expensesHref = useMemo(
    () =>
      expensesHrefForRange(
        dateFrom || data?.date_from,
        dateTo || data?.date_to
      ),
    [dateFrom, dateTo, data?.date_from, data?.date_to]
  );

  return (
    <PageShell>
      <PageHeader
        title="Trading profit"
        description="Trading profit (accrual, includes unpaid) and cash trading profit (money collected) — this week, month, year, or any past date range. Click any figure to see how it was calculated."
      >
        <Button variant="outline" size="sm" onClick={() => navigate('/reports')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
      </PageHeader>

      <div className="mb-4 space-y-3">
        <PeriodPills
          value={period === 'custom' ? null : period}
          onChange={onPresetChange}
          size="default"
          periods={PROFIT_PERIODS}
        />
        <FilterBar>
          <FilterField label="From">
            <Input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </FilterField>
          <FilterField label="To">
            <Input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </FilterField>
          <FilterField label=" ">
            <Button
              type="button"
              size="sm"
              onClick={applyCustomRange}
              disabled={loading || !dateFrom || !dateTo}
            >
              Apply dates
            </Button>
          </FilterField>
        </FilterBar>
        <p className="text-xs text-muted-foreground">
          Use the pills for the current week/month/year, or set From / To to backdate (e.g. last
          month or a past week). Click a line amount to open its calculation.
        </p>
      </div>

      {loading ? <PageLoading rows={4} /> : null}
      {!loading && error ? (
        <EmptyState title="Unavailable" description={error} />
      ) : null}
      {!loading && !error && summary ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card
            className={cn(
              isLoss && 'border-destructive/25 bg-destructive/[0.04] text-destructive'
            )}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    'rounded-md p-2',
                    isLoss ? 'bg-destructive/10 text-destructive' : 'bg-primary/10 text-primary'
                  )}
                >
                  <TrendIcon className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle
                    className={cn('text-base', isLoss && 'text-destructive')}
                  >
                    {isLoss ? 'Trading loss' : 'Trading profit'}
                  </CardTitle>
                  <p
                    className={cn(
                      'text-xs capitalize',
                      isLoss ? 'text-destructive/70' : 'text-muted-foreground'
                    )}
                  >
                    {rangeLabel} · accrual (includes unpaid / debt)
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <button
                type="button"
                onClick={() => openBreakdown('net_profit')}
                className={cn(
                  'text-left text-3xl font-semibold tabular-nums tracking-tight hover:underline',
                  isLoss && 'text-destructive'
                )}
              >
                {formatCurrency(summary.net_profit)}
              </button>
              <p
                className={cn(
                  'mt-1 text-xs',
                  isLoss ? 'text-destructive/70' : 'text-muted-foreground'
                )}
              >
                Margin {summary.profit_margin}% of net sales
              </p>
              {Number(summary.unpaid_on_sales) > 0 ? (
                <button
                  type="button"
                  onClick={() => openBreakdown('unpaid_on_sales')}
                  className="mt-3 block w-full rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-left text-xs text-amber-950 hover:underline dark:text-amber-100"
                >
                  Includes {formatCurrency(summary.unpaid_on_sales)} still unpaid on these
                  sales — counted in trading profit, not yet in the till.
                </button>
              ) : null}
            </CardContent>
          </Card>

          <Card
            className={cn(
              isCashLoss && 'border-destructive/25 bg-destructive/[0.04] text-destructive'
            )}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    'rounded-md p-2',
                    isCashLoss
                      ? 'bg-destructive/10 text-destructive'
                      : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                  )}
                >
                  <CashTrendIcon className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle
                    className={cn('text-base', isCashLoss && 'text-destructive')}
                  >
                    {isCashLoss ? 'Cash trading loss' : 'Cash trading profit'}
                  </CardTitle>
                  <p
                    className={cn(
                      'text-xs capitalize',
                      isCashLoss ? 'text-destructive/70' : 'text-muted-foreground'
                    )}
                  >
                    {rangeLabel} · cash collected only
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <button
                type="button"
                onClick={() => openBreakdown('cash_net_profit')}
                className={cn(
                  'text-left text-3xl font-semibold tabular-nums tracking-tight hover:underline',
                  isCashLoss && 'text-destructive'
                )}
              >
                {formatCurrency(summary.cash_net_profit ?? 0)}
              </button>
              <p
                className={cn(
                  'mt-1 text-xs',
                  isCashLoss ? 'text-destructive/70' : 'text-muted-foreground'
                )}
              >
                Margin {summary.cash_profit_margin ?? 0}% of cash in
              </p>
              <button
                type="button"
                onClick={() => openBreakdown('cash_in_period')}
                className="mt-3 block text-left text-xs text-muted-foreground hover:underline"
              >
                Cash in {formatCurrency(summary.cash_in_period ?? 0)} − same COGS &amp;
                expenses as trading profit.
              </button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Trading profit (accrual)</CardTitle>
              <p className="text-xs text-muted-foreground">
                Net sales − COGS − expenses + other income · click any line
              </p>
            </CardHeader>
            <CardContent className="space-y-0">
              <Row
                label="Gross sales"
                value={summary.gross_sales}
                onClick={() => openBreakdown('gross_sales')}
              />
              <Row
                label="Refunds / voids"
                value={summary.refunds}
                muted
                onClick={() => openBreakdown('refunds')}
              />
              <Row
                label="Net sales"
                value={summary.net_sales}
                emphasize
                onClick={() => openBreakdown('net_sales')}
              />
              <Row
                label="COGS (cost of goods sold)"
                value={summary.cogs}
                onClick={() => openBreakdown('cogs')}
              />
              <Row
                label="Gross profit"
                value={summary.gross_profit}
                emphasize
                onClick={() => openBreakdown('gross_profit')}
              />
              <Row
                label="Expenses (in trading profit)"
                value={summary.expenses}
                onClick={() => openBreakdown('expenses')}
              />
              {Number(summary.expenses_excluded) > 0 ? (
                <Row
                  label={`Excluded expenses (${summary.expenses_excluded_count || 0})`}
                  value={summary.expenses_excluded}
                  muted
                  onClick={() => openBreakdown('expenses_excluded')}
                />
              ) : null}
              <Row
                label="Other income"
                value={summary.other_income}
                muted
                onClick={() => openBreakdown('other_income')}
              />
              <Row
                label="Trading profit"
                value={summary.net_profit}
                emphasize
                onClick={() => openBreakdown('net_profit')}
              />
              {expensesHref ? (
                <p className="pt-2 text-xs text-muted-foreground">
                  <Link to={expensesHref} className="text-primary hover:underline">
                    Open expenses list for this range
                  </Link>
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Cash trading profit</CardTitle>
              <p className="text-xs text-muted-foreground">
                (Collected + debt collections) − COGS − expenses + other income · click any line
              </p>
            </CardHeader>
            <CardContent className="space-y-0">
              <Row
                label="Collected on these sales"
                value={summary.collected_on_sales ?? 0}
                onClick={() => openBreakdown('collected_on_sales')}
              />
              <Row
                label="Debt collections this period"
                value={summary.debt_collections ?? 0}
                muted
                onClick={() => openBreakdown('debt_collections')}
              />
              <Row
                label="Cash in"
                value={summary.cash_in_period ?? 0}
                emphasize
                onClick={() => openBreakdown('cash_in_period')}
              />
              <Row
                label="Still unpaid on these sales"
                value={summary.unpaid_on_sales ?? 0}
                emphasize={Number(summary.unpaid_on_sales) > 0}
                onClick={() => openBreakdown('unpaid_on_sales')}
              />
              <Row
                label="COGS (same as accrual)"
                value={summary.cogs}
                muted
                onClick={() => openBreakdown('cogs')}
              />
              <Row
                label="Cash gross profit"
                value={summary.cash_gross_profit ?? 0}
                emphasize
                onClick={() => openBreakdown('cash_gross_profit')}
              />
              <Row
                label="Expenses"
                value={summary.expenses}
                muted
                onClick={() => openBreakdown('expenses')}
              />
              <Row
                label="Other income"
                value={summary.other_income}
                muted
                onClick={() => openBreakdown('other_income')}
              />
              <Row
                label="Cash trading profit"
                value={summary.cash_net_profit ?? 0}
                emphasize
                onClick={() => openBreakdown('cash_net_profit')}
              />
              <p className="pt-3 text-xs text-muted-foreground">
                {summary.cash_vs_debt_note ||
                  'When customers still owe, cash trading profit is lower than trading profit.'}
              </p>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Notes</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-1">
              <p>
                Sales use business date; refunds use when the void was applied; expenses use
                expense date. Pending voids do not change these numbers until approved.
                Admins can turn off “Include in trading profit” on an expense category
                (Expenses → Manage categories) so that category’s spend does not reduce
                trading profit.
              </p>
              <p>
                Purchases this period ({formatCurrency(summary.purchases)}) are shown for
                context only — they are not subtracted from profit (buying stock is not the
                same as COGS).
              </p>
              <p>
                Tax included in sales totals this period:{' '}
                {formatCurrency(summary.tax_amount)}.
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <BreakdownDialog
        open={drillOpen}
        onOpenChange={setDrillOpen}
        loading={drillLoading}
        error={drillError}
        data={drillData}
      />
    </PageShell>
  );
}
