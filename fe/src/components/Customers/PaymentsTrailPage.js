import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Banknote, Search } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { customerDetailPath, formatDebtTrail } from '../../utils/customerDetail';
import {
  getTodayDateString,
  shiftDate,
  settlementMethodLabel,
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
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ListPaginationRail,
} from '../page';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';

const KIND_OPTIONS = [
  { id: 'all', name: 'All payments' },
  { id: 'debt_settlement', name: 'Debt collections' },
  { id: 'invoice_payment', name: 'Invoice payments' },
  { id: 'sale_payment', name: 'Sale tender' },
];

const KIND_LABELS = {
  debt_settlement: 'Debt collection',
  invoice_payment: 'Invoice payment',
  sale_payment: 'Sale tender',
};

function defaultDateFrom() {
  return shiftDate(getTodayDateString(), -30);
}

export default function PaymentsTrailPage() {
  const [kind, setKind] = useState('all');
  const [dateFrom, setDateFrom] = useState(defaultDateFrom);
  const [dateTo, setDateTo] = useState(getTodayDateString);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: pageSize,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      if (kind && kind !== 'all') params.kind = kind;
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
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
  }, [kind, dateFrom, dateTo, debouncedSearch, page, pageSize]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [kind, dateFrom, dateTo, debouncedSearch]);

  return (
    <PageShell>
      <PageHeader
        title="Payments trail"
        description="Every payment in, what it settled, and the debt balance after — for audit and balancing."
      />

      <FilterBar>
        <FilterField label="Type">
          <SearchableSelect
            value={kind}
            onChange={(e) => setKind(e.target.value || 'all')}
            options={KIND_OPTIONS}
            placeholder="Payment type"
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
        <FilterField label="Search" className="min-w-[14rem] flex-1">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Customer, sale, invoice, or reference"
              className="h-9 pl-8"
            />
          </div>
        </FilterField>
        <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </FilterBar>

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
              <DataTableHead>Reference</DataTableHead>
              <DataTableHead>Paid towards</DataTableHead>
              <DataTableHead>Balance trail</DataTableHead>
              <DataTableHead>Collected by</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {rows.map((row) => (
                <DataTableRow key={`${row.kind}-${row.id}`}>
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
                  <DataTableCell className="font-mono text-sm">
                    {settlementReferenceLabel(row)}
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
    </PageShell>
  );
}
