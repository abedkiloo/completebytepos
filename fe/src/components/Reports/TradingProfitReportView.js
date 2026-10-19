import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, TrendingUp } from 'lucide-react';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { DEFAULT_REPORT_PERIOD } from '../../utils/reportPeriods';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import PeriodPills from './PeriodPills';

const PROFIT_PERIODS = [
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'year', label: 'This year' },
];

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
  const [period, setPeriod] = useState(
    PROFIT_PERIODS.some((p) => p.id === DEFAULT_REPORT_PERIOD)
      ? DEFAULT_REPORT_PERIOD
      : 'month'
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await reportsAPI.tradingProfit({ period });
      setData(res.data);
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
  }, [period]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = data?.summary;

  return (
    <PageShell>
      <PageHeader
        title="Trading profit"
        description="Net sales minus cost of goods sold and expenses, for this week, month, or year."
      >
        <Button variant="outline" size="sm" onClick={() => navigate('/reports')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
      </PageHeader>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <PeriodPills
          value={period}
          onChange={setPeriod}
          size="default"
          periods={PROFIT_PERIODS}
        />
      </div>

      {loading ? <PageLoading rows={4} /> : null}
      {!loading && error ? (
        <EmptyState title="Unavailable" description={error} />
      ) : null}
      {!loading && !error && summary ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <div className="rounded-md bg-primary/10 p-2 text-primary">
                  <TrendingUp className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-base">Net profit</CardTitle>
                  <p className="text-xs text-muted-foreground capitalize">
                    {data.period} · trading basis
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tabular-nums tracking-tight">
                {formatCurrency(summary.net_profit)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
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
