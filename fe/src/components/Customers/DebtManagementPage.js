import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Wallet,
  Users,
  TrendingDown,
  Banknote,
  History,
  Search,
  ExternalLink,
} from 'lucide-react';

import { customersAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import {
  customersShowWalletBalance,
  customersEnableWalletPayment,
} from '../../utils/customerDisplay';
import {
  AGING_BUCKET_LABELS,
  AGING_BUCKET_OPTIONS,
  emptyDebtSummary,
  walletTxnLabel,
} from '../../utils/debtManagement';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import SearchableSelect from '../Shared/SearchableSelect';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  SummaryCard,
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

const ORDER_OPTIONS = [
  { id: '-debt_amount', name: 'Highest debt' },
  { id: 'debt_amount', name: 'Lowest debt' },
  { id: '-debt_age_days', name: 'Oldest first' },
  { id: 'debt_age_days', name: 'Newest first' },
  { id: 'name', name: 'Name A–Z' },
];

export default function DebtManagementPage() {
  const { permissions } = getStoredAuth();
  const { settings: customerSettings, loading: settingsLoading } = useModuleSettings('customers');
  const showWallet = customersShowWalletBalance(customerSettings);
  const canCollect =
    hasPermission(permissions, 'customers', 'update') &&
    customersEnableWalletPayment(customerSettings);

  const [summary, setSummary] = useState(emptyDebtSummary());
  const [debtors, setDebtors] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 350);
  const [agingBucket, setAgingBucket] = useState('');
  const [ordering, setOrdering] = useState('-debt_amount');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);
  const [payCustomer, setPayCustomer] = useState(null);
  const [historyCustomer, setHistoryCustomer] = useState(null);
  const [historyTxns, setHistoryTxns] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!showWallet) {
      setSummary(emptyDebtSummary());
      return;
    }
    try {
      const res = await customersAPI.debtSummary();
      setSummary({ ...emptyDebtSummary(), ...(res.data || {}) });
    } catch {
      setSummary(emptyDebtSummary());
    }
  }, [showWallet]);

  const loadDebtors = useCallback(async () => {
    if (!showWallet) {
      setDebtors([]);
      setCount(0);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await customersAPI.debtors({
        search: debouncedSearch.trim() || undefined,
        aging_bucket: agingBucket || undefined,
        ordering,
        page,
        page_size: pageSize,
      });
      setDebtors(res.data?.results || []);
      setCount(res.data?.count || 0);
    } catch (err) {
      setDebtors([]);
      setCount(0);
      const msg = err.response?.data?.error || 'Could not load debtors';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [showWallet, debouncedSearch, agingBucket, ordering, page, pageSize]);

  useEffect(() => {
    if (settingsLoading) return;
    loadSummary();
  }, [settingsLoading, loadSummary]);

  useEffect(() => {
    if (settingsLoading) return;
    loadDebtors();
  }, [settingsLoading, loadDebtors]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadSummary(), loadDebtors()]);
    dispatchNavBadgesRefresh();
  }, [loadSummary, loadDebtors]);

  const openHistory = async (row) => {
    setHistoryCustomer(row);
    setHistoryLoading(true);
    setHistoryTxns([]);
    try {
      const res = await customersAPI.walletTransactions(row.id, { limit: 40 });
      setHistoryTxns(res.data || []);
    } catch {
      toast.error('Could not load wallet history');
      setHistoryTxns([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const agingCards = useMemo(
    () =>
      Object.keys(AGING_BUCKET_LABELS).map((key) => ({
        key,
        label: AGING_BUCKET_LABELS[key],
        count: summary.aging?.[key]?.count || 0,
        amount: summary.aging?.[key]?.amount || '0.00',
      })),
    [summary]
  );

  if (settingsLoading) {
    return <PageLoading rows={6} />;
  }

  if (!showWallet) {
    return (
      <PageShell>
        <PageHeader
          title="Debt Management"
          description="Track customers who owe money from pay-later and partial payments."
        />
        <EmptyState
          icon={Wallet}
          title="Wallet debt is hidden"
          description="Turn on “Show wallet balance” in Customers module settings to use Debt Management."
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title="Debt Management"
        description="See who owes money, how old the debt is, and collect payments."
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={Users}
          label="Customers with debt"
          value={(summary.customers_with_debt || 0).toLocaleString()}
          tone={summary.customers_with_debt > 0 ? 'warning' : 'default'}
        />
        <SummaryCard
          icon={TrendingDown}
          label="Total debt outstanding"
          value={formatCurrency(summary.total_debt)}
          tone={Number(summary.total_debt) > 0 ? 'destructive' : 'default'}
        />
        <SummaryCard
          icon={Wallet}
          label="Average debt"
          value={formatCurrency(summary.average_debt)}
        />
        <SummaryCard
          icon={Banknote}
          label="Collected today"
          value={formatCurrency(summary.collected_today)}
          tone={Number(summary.collected_today) > 0 ? 'success' : 'default'}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {agingCards.map((bucket) => (
          <button
            key={bucket.key}
            type="button"
            onClick={() => {
              setAgingBucket((prev) => (prev === bucket.key ? '' : bucket.key));
              setPage(1);
            }}
            className={`rounded-lg border p-3 text-left transition-colors ${
              agingBucket === bucket.key
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted/40'
            }`}
          >
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {bucket.label}
            </p>
            <p className="mt-1 text-lg font-bold tabular-nums">{bucket.count}</p>
            <p className="text-sm text-muted-foreground">{formatCurrency(bucket.amount)}</p>
          </button>
        ))}
      </div>

      <FilterBar>
        <FilterField label="Search" className="min-w-[200px] flex-[2]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Name, phone, or code…"
              className="h-10 pl-9"
            />
          </div>
        </FilterField>
        <FilterField label="Age">
          <SearchableSelect
            value={agingBucket}
            onChange={(e) => {
              setAgingBucket(e.target.value);
              setPage(1);
            }}
            options={AGING_BUCKET_OPTIONS}
            placeholder="All ages"
          />
        </FilterField>
        <FilterField label="Sort">
          <SearchableSelect
            value={ordering}
            onChange={(e) => {
              setOrdering(e.target.value);
              setPage(1);
            }}
            options={ORDER_OPTIONS}
            placeholder="Sort"
          />
        </FilterField>
      </FilterBar>

      {loading && debtors.length === 0 ? (
        <PageLoading rows={6} />
      ) : debtors.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title="No customers with debt"
          description={
            search || agingBucket
              ? 'Try clearing filters, or check Sales for pay-later balances.'
              : 'When sales are put on account, debtors will appear here.'
          }
        />
      ) : (
        <ListPaginationRail
          page={page}
          pageSize={pageSize}
          totalCount={count}
          suffix={`${count} debtor${count === 1 ? '' : 's'}`}
          onPageChange={setPage}
        >
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Customer</DataTableHead>
              <DataTableHead align="right">Debt</DataTableHead>
              <DataTableHead>Age</DataTableHead>
              <DataTableHead>Last sale</DataTableHead>
              <DataTableHead>Last payment</DataTableHead>
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {debtors.map((row) => (
                <DataTableRow key={row.id}>
                  <DataTableCell>
                    <div className="font-medium">{row.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {[row.phone, row.customer_code].filter(Boolean).join(' · ') || '—'}
                    </div>
                  </DataTableCell>
                  <DataTableCell align="right" className="font-semibold text-destructive">
                    {formatCurrency(row.debt_amount)}
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant="secondary">
                      {row.debt_age_days}d · {AGING_BUCKET_LABELS[row.aging_bucket] || row.aging_bucket}
                    </Badge>
                  </DataTableCell>
                  <DataTableCell className="text-muted-foreground whitespace-nowrap text-sm">
                    {row.last_sale_at ? formatDateTime(row.last_sale_at) : '—'}
                  </DataTableCell>
                  <DataTableCell className="text-muted-foreground whitespace-nowrap text-sm">
                    {row.last_payment_at ? formatDateTime(row.last_payment_at) : '—'}
                  </DataTableCell>
                  <DataTableCell align="right">
                    <div className="flex flex-wrap justify-end gap-1">
                      {canCollect && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() =>
                            setPayCustomer({
                              id: row.id,
                              name: row.name,
                              phone: row.phone,
                              wallet_balance: row.wallet_balance,
                            })
                          }
                        >
                          Receive payment
                        </Button>
                      )}
                      <Button variant="outline" size="sm" onClick={() => openHistory(row)}>
                        <History className="mr-1 h-3.5 w-3.5" />
                        History
                      </Button>
                      <Link
                        to="/customers"
                        state={{ focusCustomerId: row.id }}
                        className="inline-flex h-8 items-center gap-1 rounded-md px-2.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        Customer
                      </Link>
                    </div>
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </ListPaginationRail>
      )}

      <ReceiveWalletPaymentDialog
        open={Boolean(payCustomer)}
        customer={payCustomer}
        onOpenChange={(open) => {
          if (!open) setPayCustomer(null);
        }}
        onSuccess={() => {
          setPayCustomer(null);
          refreshAll();
        }}
      />

      <Dialog
        open={Boolean(historyCustomer)}
        onOpenChange={(open) => {
          if (!open) {
            setHistoryCustomer(null);
            setHistoryTxns([]);
          }
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Wallet history — {historyCustomer?.name}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Balance {formatCurrency(historyCustomer?.wallet_balance)} · owed{' '}
            {formatCurrency(historyCustomer?.debt_amount)}
          </p>
          {historyLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
          ) : historyTxns.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No transactions yet.</p>
          ) : (
            <ul className="space-y-2">
              {historyTxns.map((txn) => (
                <li
                  key={txn.id}
                  className="rounded-md border px-3 py-2 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{walletTxnLabel(txn.source_type)}</div>
                      <div className="text-xs text-muted-foreground">
                        {formatDateTime(txn.created_at)}
                        {txn.sale_number || txn.sale?.sale_number
                          ? ` · ${txn.sale_number || txn.sale.sale_number}`
                          : ''}
                      </div>
                      {txn.notes ? (
                        <div className="mt-1 text-xs text-muted-foreground">{txn.notes}</div>
                      ) : null}
                    </div>
                    <div
                      className={`shrink-0 font-semibold tabular-nums ${
                        txn.transaction_type === 'credit' ? 'text-success' : 'text-destructive'
                      }`}
                    >
                      {txn.transaction_type === 'credit' ? '+' : '−'}
                      {formatCurrency(txn.amount)}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <DialogFooter className="gap-2 sm:justify-between">
            {canCollect && historyCustomer && (
              <Button
                onClick={() => {
                  setPayCustomer({
                    id: historyCustomer.id,
                    name: historyCustomer.name,
                    phone: historyCustomer.phone,
                    wallet_balance: historyCustomer.wallet_balance,
                  });
                  setHistoryCustomer(null);
                }}
              >
                Receive payment
              </Button>
            )}
            <Button variant="outline" onClick={() => setHistoryCustomer(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
