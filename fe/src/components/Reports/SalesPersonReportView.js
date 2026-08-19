import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Printer, UserRound } from 'lucide-react';

import { reportsAPI, usersAPI } from '../../services/api';
import { formatCurrency, formatDateTime, formatNumber } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { EmptyState, FilterBar, FilterField, PageLoading } from '../page';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { R } from './reportUI';
import PeriodPills from './PeriodPills';
import { DEFAULT_REPORT_PERIOD } from '../../utils/reportPeriods';
import ReportExportButtons from './ReportExportButtons';

function currentMonthValue() {
  const now = new Date();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${now.getFullYear()}-${m}`;
}

function staffLabel(user) {
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
  return name || user.username;
}

export default function SalesPersonReportView() {
  const [periodPreset, setPeriodPreset] = useState(DEFAULT_REPORT_PERIOD);
  const [month, setMonth] = useState(currentMonthValue());
  const [useCalendarMonth, setUseCalendarMonth] = useState(false);
  const [cashierId, setCashierId] = useState('all');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [staffOptions, setStaffOptions] = useState([]);

  const queryParams = useMemo(() => {
    const params = useCalendarMonth ? { month } : { period: periodPreset };
    if (cashierId && cashierId !== 'all') {
      params.cashier_id = cashierId;
    }
    return params;
  }, [useCalendarMonth, month, periodPreset, cashierId]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const response = await reportsAPI.salesByPerson(queryParams);
      setData(response.data);
    } catch (error) {
      setData(null);
      toast.error('Could not load sales staff report');
    } finally {
      setLoading(false);
    }
  }, [queryParams]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  useEffect(() => {
    usersAPI
      .list({ is_active: true })
      .then((res) => {
        const rows = res.data?.results || res.data || [];
        setStaffOptions(Array.isArray(rows) ? rows : []);
      })
      .catch(() => setStaffOptions([]));
  }, []);

  return (
    <div className="sales-person-report space-y-6 print:space-y-4">
      <FilterBar className="print:hidden">
        <FilterField label="Period" className="sm:col-span-2">
          <PeriodPills
            value={useCalendarMonth ? 'custom' : periodPreset}
            onChange={(periodId) => {
              setUseCalendarMonth(false);
              setPeriodPreset(periodId);
            }}
            size="default"
          />
        </FilterField>
        <FilterField label="Or pick month">
          <Input
            type="month"
            value={month}
            onChange={(e) => {
              setMonth(e.target.value);
              setUseCalendarMonth(true);
            }}
          />
        </FilterField>
        <FilterField label="Staff member">
          <select
            value={cashierId}
            onChange={(e) => setCashierId(e.target.value)}
            className="flex h-10 w-full min-w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="all">All staff</option>
            {staffOptions.map((user) => (
              <option key={user.id} value={String(user.id)}>
                {staffLabel(user)}
              </option>
            ))}
          </select>
        </FilterField>
        <div className="flex flex-wrap items-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
            <Printer className="mr-2 h-4 w-4" />
            Print
          </Button>
          <ReportExportButtons slug="sales-by-person" params={queryParams} disabled={loading} />
        </div>
      </FilterBar>

      {loading ? (
        <PageLoading rows={8} showStats />
      ) : !data?.staff?.length ? (
        <EmptyState
          icon={UserRound}
          title="No sales for this period"
          description="Pick another month or confirm completed sales exist for your team."
        />
      ) : (
        <>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">{data.period_display || data.period}</h2>
              <p className="text-sm text-muted-foreground">
                Performance by sales person — net sales after refunds in this period.
              </p>
            </div>
          </div>

          <p className="rounded-md border border-dashed bg-muted/30 px-3 py-2 text-xs text-muted-foreground print:border-0 print:bg-transparent">
            {data.note}
          </p>

          <div className={R.summaryGrid}>
            <div className={R.summaryCard}>
              <h3>Completed sales</h3>
              <p className={R.summaryValue}>{formatNumber(data.summary.sales_count)}</p>
            </div>
            <div className={R.summaryCard}>
              <h3>Gross sales</h3>
              <p className={R.summaryValue}>{formatCurrency(data.summary.gross_sales)}</p>
            </div>
            <div className={R.summaryCard}>
              <h3>Refunds</h3>
              <p className={R.summaryValue}>{formatCurrency(data.summary.refunds_total)}</p>
            </div>
            <div className={R.summaryCard}>
              <h3>Net sales</h3>
              <p className={R.summaryValue}>{formatCurrency(data.summary.net_sales)}</p>
            </div>
          </div>

          <div className={R.tableWrap}>
            <table className={R.table}>
              <thead>
                <tr>
                  <th>Staff member</th>
                  <th>Sales</th>
                  <th>Gross</th>
                  <th>Refunds</th>
                  <th>Net sales</th>
                  <th>Items</th>
                  <th>Avg ticket</th>
                </tr>
              </thead>
              <tbody>
                {data.staff.map((row) => (
                  <tr key={row.user_id ?? `unassigned-${row.username}`}>
                    <td>
                      <div className="font-medium">{row.display_name}</div>
                      {row.username ? (
                        <div className="text-xs text-muted-foreground">@{row.username}</div>
                      ) : null}
                    </td>
                    <td>{formatNumber(row.sales_count)}</td>
                    <td>{formatCurrency(row.gross_sales)}</td>
                    <td>
                      {row.refunds_count > 0 ? (
                        <span>
                          {formatCurrency(row.refunds_total)}{' '}
                          <span className="text-xs text-muted-foreground">
                            ({row.refunds_count})
                          </span>
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="font-medium">{formatCurrency(row.net_sales)}</td>
                    <td>{formatNumber(row.items_sold)}</td>
                    <td>{formatCurrency(row.avg_ticket)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.transactions?.length > 0 ? (
            <div>
              <h3 className="mb-2 text-base font-semibold">Transaction detail</h3>
              <div className={R.tableWrap}>
                <table className={R.table}>
                  <thead>
                    <tr>
                      <th>Sale #</th>
                      <th>Date</th>
                      <th>Payment</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map((tx) => (
                      <tr key={tx.sale_id}>
                        <td>{tx.sale_number}</td>
                        <td>{formatDateTime(tx.date)}</td>
                        <td className="capitalize">{tx.payment_method}</td>
                        <td>{formatCurrency(tx.net)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
