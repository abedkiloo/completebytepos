import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Banknote, Calculator, FileSpreadsheet, Search } from 'lucide-react';

import { customersAPI, salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { isModuleFeatureEnabled } from '../../utils/moduleFeatures';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { customerDetailPath, formatDebtTrail } from '../../utils/customerDetail';
import {
  getTodayDateString,
  isPaymentsTrailTodayRange,
  paymentsTrailLast30DaysRange,
  paymentsTrailTodayRange,
  settlementMethodLabel,
  settlementPayerLabel,
  settlementReferenceLabel,
} from '../../utils/debtManagement';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import SearchableSelect from '../Shared/SearchableSelect';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  FilterField,
  SummaryCard,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ListPaginationRail,
} from '../page';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import ReceiptImageLink from '../Shared/ReceiptImageLink';
import PaymentDetailDialog from './PaymentDetailDialog';
import SaleDetailDialog from '../Sales/SaleDetailDialog';

const KIND_OPTIONS = [
  { id: 'all', name: 'All payments' },
  { id: 'debt_settlement', name: 'Debt collections' },
  { id: 'invoice_payment', name: 'Invoice payments' },
  { id: 'sale_payment', name: 'Sale tender' },
];

const MPESA_VIA_OPTIONS = [
  { id: '', name: 'Till or bank' },
  { id: 'till', name: 'Till only' },
  { id: 'bank', name: 'Bank only' },
];

const KIND_LABELS = {
  debt_settlement: 'Debt collection',
  invoice_payment: 'Invoice payment',
  sale_payment: 'Sale tender',
};

function defaultDateFrom() {
  return paymentsTrailLast30DaysRange().dateFrom;
}

export default function PaymentsTrailPage() {
  const { permissions } = getStoredAuth();
  const allowed = hasPermission(permissions, 'debt_management', 'payments_trail');
  const canExport = allowed && isModuleFeatureEnabled('sales', 'payments_trail_export', true);
  const [kind, setKind] = useState('all');
  const [mpesaDestination, setMpesaDestination] = useState('');
  const [dateFrom, setDateFrom] = useState(defaultDateFrom);
  const [dateTo, setDateTo] = useState(getTodayDateString);
  const todaySelected = isPaymentsTrailTodayRange(dateFrom, dateTo);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [exportBusy, setExportBusy] = useState(false);
  const [totalBusy, setTotalBusy] = useState(false);
  const [rangeTotal, setRangeTotal] = useState(null);
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [paymentDetailOpen, setPaymentDetailOpen] = useState(false);
  const [paymentDetailLoading, setPaymentDetailLoading] = useState(false);
  const [selectedSale, setSelectedSale] = useState(null);
  const [saleDetailOpen, setSaleDetailOpen] = useState(false);

  const openPayment = async (row) => {
    if (!row?.id) return;
    if (row.kind === 'sale_payment') {
      try {
        const res = await salesAPI.get(row.id);
        setSelectedSale(res.data);
        setSaleDetailOpen(true);
      } catch (err) {
        toast.error(err.response?.data?.error || 'Could not open sale detail');
      }
      return;
    }
    if (row.kind === 'debt_settlement') {
      setSelectedPayment({ ...row, kind: 'debt_settlement' });
      setPaymentDetailOpen(true);
      setPaymentDetailLoading(true);
      try {
        const res = await customersAPI.walletSettlementDetail(row.id);
        setSelectedPayment(res.data);
      } catch {
        /* list row is enough when refresh fails */
      } finally {
        setPaymentDetailLoading(false);
      }
      return;
    }
    setSelectedPayment(row);
    setPaymentDetailOpen(true);
    setPaymentDetailLoading(false);
  };

  const trailFilterParams = useCallback(() => {
    const params = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    if (kind && kind !== 'all') params.kind = kind;
    if (mpesaDestination) {
      params.mpesa_destination = mpesaDestination;
      if (!params.kind) params.kind = 'debt_settlement';
    }
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
    return params;
  }, [kind, mpesaDestination, dateFrom, dateTo, debouncedSearch]);

  const handleExportExcel = async () => {
    if (!canExport || exportBusy) return;
    setExportBusy(true);
    try {
      await customersAPI.paymentsTrailExport(trailFilterParams());
      toast.success('Payments Excel downloaded');
    } catch (err) {
      toast.error(err.message || err.response?.data?.error || 'Could not download Excel');
    } finally {
      setExportBusy(false);
    }
  };

  const handleShowTotal = async () => {
    if (!allowed || totalBusy) return;
    setTotalBusy(true);
    try {
      const res = await customersAPI.paymentsTrailSummary(trailFilterParams());
      setRangeTotal(res.data || null);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not calculate total');
      setRangeTotal(null);
    } finally {
      setTotalBusy(false);
    }
  };

  const load = useCallback(async () => {
    if (!allowed) {
      setLoading(false);
      setRows([]);
      setCount(0);
      return;
    }
    setLoading(true);
    try {
      const params = {
        page,
        page_size: pageSize,
        ...trailFilterParams(),
      };
      const res = await customersAPI.paymentsTrail(params);
      setRows(res.data?.results || []);
      setCount(Number(res.data?.count || 0));
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not load payments trail');
      setRows([]);
      setCount(0);
    } finally {
      setLoading(false);
    }
  }, [allowed, page, pageSize, trailFilterParams]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
    setRangeTotal(null);
  }, [kind, mpesaDestination, dateFrom, dateTo, debouncedSearch]);

  if (!allowed) {
    return (
      <PageShell>
        <PageHeader
          title="Payments trail"
          description="Every payment in, what it settled, and the debt balance after — for audit and balancing."
        />
        <EmptyState
          icon={Banknote}
          title="Payments trail is restricted"
          description="Only managers (or roles with Payments trail permission) can open this page. Ask an admin if you need access."
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title="Payments trail"
        description="Every payment in once: checkout tender, debt collections, and invoice payments. A collection that clears a debt sale is not listed again as sale tender. Download Excel for the selected dates."
      >
        {canExport ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleExportExcel}
            disabled={exportBusy || loading}
            aria-label="Download payments Excel"
          >
            <FileSpreadsheet className="h-4 w-4 mr-1.5" />
            {exportBusy ? 'Downloading…' : 'Download Excel'}
          </Button>
        ) : null}
      </PageHeader>

      <FilterBar>
        <FilterField label="Type">
          <SearchableSelect
            value={kind}
            onChange={(e) => setKind(e.target.value || 'all')}
            options={KIND_OPTIONS}
            placeholder="Payment type"
          />
        </FilterField>
        <FilterField label="M-Pesa via">
          <SearchableSelect
            value={mpesaDestination}
            onChange={(e) => setMpesaDestination(e.target.value || '')}
            options={MPESA_VIA_OPTIONS}
            placeholder="Till or bank"
          />
        </FilterField>
        <FilterField label="From">
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value || defaultDateFrom())}
            className="h-9 w-[11.5rem]"
          />
        </FilterField>
        <FilterField label="To">
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value || getTodayDateString())}
            className="h-9 w-[11.5rem]"
          />
        </FilterField>
        <div className="flex flex-wrap items-end gap-2 self-end pb-0.5">
          <Button
            type="button"
            variant={todaySelected ? 'default' : 'outline'}
            size="sm"
            data-testid="payments-trail-today"
            aria-pressed={todaySelected}
            onClick={() => {
              const range = paymentsTrailTodayRange();
              setDateFrom(range.dateFrom);
              setDateTo(range.dateTo);
            }}
          >
            Today
          </Button>
          <Button
            type="button"
            variant={!todaySelected ? 'secondary' : 'outline'}
            size="sm"
            data-testid="payments-trail-last-30"
            onClick={() => {
              const range = paymentsTrailLast30DaysRange();
              setDateFrom(range.dateFrom);
              setDateTo(range.dateTo);
            }}
          >
            Last 30 days
          </Button>
        </div>
        <FilterField label="Search" className="min-w-[14rem] flex-1">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Customer, payer, sale, invoice, or code"
              className="h-9 pl-8"
            />
          </div>
        </FilterField>
        <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleShowTotal}
          disabled={totalBusy || loading}
          aria-label="Show total for selected range"
        >
          <Calculator className="h-4 w-4 mr-1.5" />
          {totalBusy ? 'Calculating…' : 'Show total'}
        </Button>
      </FilterBar>

      {rangeTotal ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard
            icon={Banknote}
            label="Range total"
            value={formatCurrency(rangeTotal.total_amount)}
            subtext={`${rangeTotal.included_count ?? rangeTotal.count ?? 0} payment${
              Number(rangeTotal.included_count ?? rangeTotal.count ?? 0) === 1 ? '' : 's'
            }${
              rangeTotal.date_from && rangeTotal.date_to
                ? ` · ${rangeTotal.date_from} → ${rangeTotal.date_to}`
                : ''
            }`}
            tone="success"
          />
          {(rangeTotal.by_method || []).map((row) => (
            <SummaryCard
              key={row.payment_method}
              icon={Calculator}
              label={row.payment_method_label || row.payment_method}
              value={formatCurrency(row.total)}
              subtext={`${row.count} payment${Number(row.count) === 1 ? '' : 's'}`}
            />
          ))}
        </div>
      ) : null}

      {loading ? (
        <PageLoading rows={6} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Banknote}
          title="No payments in this range"
          description="Debt collections, invoice payments, and sale tender appear here with what they paid towards."
        />
      ) : (
        <ListPaginationRail
          page={page}
          pageSize={pageSize}
          totalCount={count}
          suffix={`${count} payment${count === 1 ? '' : 's'}`}
          onPageChange={setPage}
        >
          <DataTable>
            <DataTableHeader>
              <DataTableHead>When</DataTableHead>
              <DataTableHead>Type</DataTableHead>
              <DataTableHead>Customer</DataTableHead>
              <DataTableHead align="right">Amount</DataTableHead>
              <DataTableHead>Method</DataTableHead>
              <DataTableHead>Paid by</DataTableHead>
              <DataTableHead>Reference</DataTableHead>
              <DataTableHead>Proof</DataTableHead>
              <DataTableHead>Paid towards</DataTableHead>
              <DataTableHead>Balance trail</DataTableHead>
              <DataTableHead>Collected by</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {rows.map((row) => (
                <DataTableRow
                  key={`${row.kind}-${row.id}`}
                  className="cursor-pointer"
                  onClick={() => openPayment(row)}
                  data-testid={`payment-trail-row-${row.kind}-${row.id}`}
                >
                  <DataTableCell className="whitespace-nowrap text-sm text-muted-foreground">
                    {row.occurred_at ? formatDateTime(row.occurred_at) : '—'}
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant="secondary" className="text-[10px]">
                      {KIND_LABELS[row.kind] || row.kind}
                    </Badge>
                  </DataTableCell>
                  <DataTableCell>
                    {row.customer_id ? (
                      <Link
                        to={customerDetailPath(row.customer_id, { tab: 'ledger' })}
                        className="font-medium hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {row.customer_name || 'Customer'}
                      </Link>
                    ) : (
                      <span className="font-medium">{row.customer_name || '—'}</span>
                    )}
                    <div className="text-xs text-muted-foreground">
                      {[row.customer_phone, row.customer_code].filter(Boolean).join(' · ') || '—'}
                    </div>
                  </DataTableCell>
                  <DataTableCell align="right" className="font-semibold text-success tabular-nums">
                    {formatCurrency(row.amount)}
                  </DataTableCell>
                  <DataTableCell className="text-sm">
                    {settlementMethodLabel(row)}
                  </DataTableCell>
                  <DataTableCell className="text-sm">
                    {row.kind === 'debt_settlement' ? settlementPayerLabel(row) : '—'}
                  </DataTableCell>
                  <DataTableCell className="font-mono text-sm">
                    {settlementReferenceLabel(row)}
                  </DataTableCell>
                  <DataTableCell className="text-sm" onClick={(e) => e.stopPropagation()}>
                    {row.receipt_image_url ? (
                      <ReceiptImageLink
                        url={row.receipt_image_url}
                        label="Screenshot"
                      />
                    ) : (
                      '—'
                    )}
                  </DataTableCell>
                  <DataTableCell className="max-w-[14rem] text-sm">
                    <div className="font-medium">{row.paid_towards_label || '—'}</div>
                    {(row.paid_towards || []).length > 1 ? (
                      <ul className="mt-0.5 space-y-0.5 text-xs text-muted-foreground">
                        {row.paid_towards.map((t, idx) => (
                          <li key={`${t.type}-${t.sale_id || t.invoice_id || idx}`}>
                            {t.label}
                            {t.amount ? ` · ${formatCurrency(t.amount)}` : ''}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </DataTableCell>
                  <DataTableCell className="max-w-[16rem] text-xs text-muted-foreground">
                    {row.kind === 'debt_settlement'
                      ? formatDebtTrail(row) || '—'
                      : row.sale_total
                        ? `Sale ${row.sale_total} · paid ${row.sale_paid || row.amount}`
                        : '—'}
                  </DataTableCell>
                  <DataTableCell className="text-sm text-muted-foreground">
                    {row.received_by || '—'}
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </ListPaginationRail>
      )}

      <PaymentDetailDialog
        payment={selectedPayment}
        open={paymentDetailOpen}
        loading={paymentDetailLoading}
        onOpenChange={(open) => {
          setPaymentDetailOpen(open);
          if (!open) setSelectedPayment(null);
        }}
      />
      <SaleDetailDialog
        sale={selectedSale}
        open={saleDetailOpen}
        onOpenChange={(open) => {
          setSaleDetailOpen(open);
          if (!open) setSelectedSale(null);
        }}
      />
    </PageShell>
  );
}
