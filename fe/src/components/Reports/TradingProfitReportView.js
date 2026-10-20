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
      className="text-left text-sm font-medium text-primary underline-offset-2 hover:underline"
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
  const [cogsOpen, setCogsOpen] = useState(false);
  const [cogsLoading, setCogsLoading] = useState(false);
  const [cogsError, setCogsError] = useState('');
  const [cogsData, setCogsData] = useState(null);

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
      // Keep date inputs in sync with the range the server actually used.
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
    // Preset pills load immediately; custom ranges load via Apply.
    if (period === 'custom') return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const openCogsBreakdown = async () => {
    setCogsOpen(true);
    setCogsLoading(true);
    setCogsError('');
    try {
      const params =
        period === 'custom'
          ? { date_from: dateFrom, date_to: dateTo }
          : { period };
      const res = await reportsAPI.tradingProfitCogs(params);
      setCogsData(res.data);
    } catch (err) {
      setCogsData(null);
      setCogsError(
        err?.response?.data?.error || 'Could not load COGS breakdown.'
      );
    } finally {
      setCogsLoading(false);
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
    // Always fetch with the dates currently in the inputs (custom params).
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
  const TrendIcon = isLoss ? TrendingDown : TrendingUp;
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
        description="Net sales minus cost of goods sold and expenses — this week, month, year, or any past date range."
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
          month or a past week).
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
                    {isLoss ? 'Net loss' : 'Net profit'}
                  </CardTitle>
                  <p
                    className={cn(
                      'text-xs capitalize',
                      isLoss ? 'text-destructive/70' : 'text-muted-foreground'
                    )}
                  >
                    {rangeLabel} · trading basis
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p
                className={cn(
                  'text-3xl font-semibold tabular-nums tracking-tight',
                  isLoss && 'text-destructive'
                )}
              >
                {formatCurrency(summary.net_profit)}
              </p>
              <p
                className={cn(
                  'mt-1 text-xs',
                  isLoss ? 'text-destructive/70' : 'text-muted-foreground'
                )}
              >
                Margin {summary.profit_margin}% of net sales
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">How we got there</CardTitle>
              <p className="text-xs text-muted-foreground">
                Net sales − COGS − expenses + other income
              </p>
            </CardHeader>
            <CardContent className="space-y-0">
              <Row label="Gross sales" value={summary.gross_sales} />
              <Row label="Refunds / voids" value={summary.refunds} muted />
              <Row label="Net sales" value={summary.net_sales} emphasize />
              <Row
                label="COGS (cost of goods sold) — click for sales"
                value={summary.cogs}
                onClick={openCogsBreakdown}
              />
              <Row label="Gross profit" value={summary.gross_profit} emphasize />
              <Row
                label="Expenses (in trading profit)"
                value={summary.expenses}
                to={expensesHref}
              />
              {Number(summary.expenses_excluded) > 0 ? (
                <Row
                  label={`Excluded expenses (${summary.expenses_excluded_count || 0})`}
                  value={summary.expenses_excluded}
                  muted
                />
              ) : null}
              <Row label="Other income" value={summary.other_income} muted />
              <Row label="Net profit" value={summary.net_profit} emphasize />
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
                Admins can turn off “Include in trading profit” on an expense so it stays in
                Expenses but does not reduce trading profit.
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

      <Dialog open={cogsOpen} onOpenChange={setCogsOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>How COGS was calculated</DialogTitle>
            <DialogDescription>
              Cost of goods sold from sale lines in this period (quantity × unit cost),
              minus cost restored on refunds.
            </DialogDescription>
          </DialogHeader>
          {cogsLoading ? <PageLoading rows={4} /> : null}
          {!cogsLoading && cogsError ? (
            <p className="text-sm text-destructive">{cogsError}</p>
          ) : null}
          {!cogsLoading && !cogsError && cogsData ? (
            <div className="space-y-4 text-sm">
              <div className="grid gap-2 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-muted-foreground">COGS sold</p>
                  <p className="font-semibold tabular-nums">
                    {formatCurrency(cogsData.cogs_sold)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Refunded cost</p>
                  <p className="font-semibold tabular-nums">
                    {formatCurrency(cogsData.cogs_refunded)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Net COGS</p>
                  <p className="font-semibold tabular-nums">
                    {formatCurrency(cogsData.cogs)}
                  </p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{cogsData.explanation}</p>
              {cogsData.truncated ? (
                <p className="text-xs text-warning">
                  Showing {cogsData.sales_shown} of {cogsData.sale_count} sales.
                </p>
              ) : null}
              <ul className="space-y-3">
                {(cogsData.sales || []).map((sale) => (
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
                    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                      {(sale.lines || []).map((line, idx) => (
                        <li key={`${sale.sale_id}-${idx}`} className="flex justify-between gap-2">
                          <span>
                            {line.product_name}
                            {line.quantity != null ? ` × ${line.quantity}` : ''}
                            {line.unit_cost != null
                              ? ` @ ${formatCurrency(line.unit_cost)}`
                              : ''}
                          </span>
                          <span className="tabular-nums">{formatCurrency(line.line_cogs)}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
              {(cogsData.refunds || []).length > 0 ? (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Refunds restoring cost
                  </p>
                  <ul className="space-y-2">
                    {cogsData.refunds.map((refund) => (
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
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
