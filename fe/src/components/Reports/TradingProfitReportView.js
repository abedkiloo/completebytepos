import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

function Row({ label, value, emphasize = false, muted = false }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/60 py-2 last:border-0">
      <span className={muted ? 'text-sm text-muted-foreground' : 'text-sm'}>{label}</span>
      <span
        className={
          emphasize
            ? 'text-base font-semibold tabular-nums'
            : 'text-sm font-medium tabular-nums'
        }
      >
        {formatCurrency(value)}
      </span>
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

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params =
        period === 'custom'
          ? { date_from: dateFrom, date_to: dateTo }
          : { period };
      const res = await reportsAPI.tradingProfit(params);
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
  }, [period, dateFrom, dateTo]);

  useEffect(() => {
    // Preset pills load immediately; custom ranges load via Apply.
    if (period === 'custom') return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

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
              <Row label="COGS (cost of goods sold)" value={summary.cogs} />
              <Row label="Gross profit" value={summary.gross_profit} emphasize />
              <Row label="Expenses (approved)" value={summary.expenses} />
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
    </PageShell>
  );
}
