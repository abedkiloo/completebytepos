import React, { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

import { payrollAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

const todayLocal = () => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const shiftDate = (iso, deltaDays) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + deltaDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

/**
 * Daily sales-agent commission (band template) with previous-day navigation.
 */
export default function AgentCommissionCard() {
  const [date, setDate] = useState(todayLocal);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (day) => {
    setLoading(true);
    setError('');
    try {
      const res = await payrollAPI.commissionDay(
        day === todayLocal() ? {} : { date: day }
      );
      setData(res.data);
    } catch (err) {
      setData(null);
      setError(
        err.response?.data?.date ||
          err.response?.data?.detail ||
          err.message ||
          'Could not load commission'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(date);
  }, [date, load]);

  const today = todayLocal();
  const bands = data?.template?.bands || [];

  return (
    <Card data-testid="agent-commission-card">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg">Daily commission</CardTitle>
            <CardDescription>
              Band awards for sales that qualify for commission — pick any past day.
              All your sales still appear in sales history; some product lines may not
              count toward the award.
            </CardDescription>
          </div>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Previous day"
              onClick={() => setDate((d) => shiftDate(d, -1))}
              disabled={loading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Input
              type="date"
              max={today}
              value={date}
              onChange={(e) => setDate(e.target.value || today)}
              className="h-9 w-[10.5rem]"
              data-testid="agent-commission-date"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Next day"
              onClick={() => setDate((d) => shiftDate(d, 1))}
              disabled={loading || date >= today}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : !data?.enabled ? (
          <p className="text-sm text-muted-foreground">
            Sales commission is turned off for this store.
          </p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Qualifying sales</p>
                <p className="text-xl font-semibold tabular-nums">
                  {formatCurrency(data.qualifying_sales)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {data.sale_count || 0} sale{(data.sale_count || 0) === 1 ? '' : 's'}
                  {data.is_today ? ' · today' : ` · ${data.date}`}
                </p>
                {Number(data.excluded_lines || 0) > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(data.excluded_lines)} in product lines that do not
                    qualify (still on your sales)
                  </p>
                ) : null}
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Commission</p>
                <p className="text-xl font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {formatCurrency(data.commission)}
                </p>
                {data.next_band ? (
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(data.next_band.sales_to_go)} to next band (
                    {formatCurrency(data.next_band.commission)})
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">Top band reached</p>
                )}
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Transport incentive</p>
                <p className="text-xl font-semibold tabular-nums">
                  {formatCurrency(data.transport?.amount || 0)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {data.transport?.note || '—'}
                </p>
              </div>
            </div>

            {bands.length > 0 ? (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Daily sales (KES)</th>
                      <th className="px-3 py-2 font-medium">Commission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bands.map((band, idx) => {
                      const active = idx === data.band_index;
                      const maxLabel = band.max == null ? 'and above' : `– ${band.max}`;
                      return (
                        <tr
                          key={`${band.min}-${band.commission}`}
                          className={active ? 'bg-primary/10 font-medium' : undefined}
                        >
                          <td className="px-3 py-1.5">
                            {band.min} {maxLabel}
                            {active ? (
                              <Badge variant="secondary" className="ml-2 text-[10px]">
                                Your band
                              </Badge>
                            ) : null}
                          </td>
                          <td className="px-3 py-1.5 tabular-nums">
                            {formatCurrency(band.commission)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
