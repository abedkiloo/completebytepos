import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Wallet,
  Users,
  TrendingDown,
  Banknote,
  History,
  Search,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  X,
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
  emptyDebtCollections,
  getTodayDateString,
  shiftDate,
  formatDateLabel,
} from '../../utils/debtManagement';
import { customerDetailPath } from '../../utils/customerDetail';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import SearchableSelect from '../Shared/SearchableSelect';
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
  const navigate = useNavigate();
  const { permissions } = getStoredAuth();
  const { settings: customerSettings, loading: settingsLoading } = useModuleSettings('customers');
  const showWallet = customersShowWalletBalance(customerSettings);
  const canCollect =
    hasPermission(permissions, 'debt_management', 'update') &&
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
  const [showCollections, setShowCollections] = useState(false);
  const [collectionDate, setCollectionDate] = useState(getTodayDateString);
  const [collections, setCollections] = useState(emptyDebtCollections());
  const [collectionsLoading, setCollectionsLoading] = useState(false);

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

  const loadCollections = useCallback(async (dateStr) => {
    if (!showWallet) {
      setCollections(emptyDebtCollections());
      return;
    }
    setCollectionsLoading(true);
    try {
      const res = await customersAPI.debtCollections({ date: dateStr, page_size: 200 });
      setCollections({ ...emptyDebtCollections(), ...(res.data || {}), date: dateStr });
    } catch (err) {
      setCollections({ ...emptyDebtCollections(), date: dateStr });
      toast.error(err.response?.data?.error || 'Could not load collections');
    } finally {
      setCollectionsLoading(false);
    }
  }, [showWallet]);

  useEffect(() => {
    if (settingsLoading) return;
    loadSummary();
  }, [settingsLoading, loadSummary]);

  useEffect(() => {
    if (settingsLoading) return;
    loadDebtors();
  }, [settingsLoading, loadDebtors]);

  useEffect(() => {
    if (settingsLoading || !showCollections) return;
    loadCollections(collectionDate);
  }, [settingsLoading, showCollections, collectionDate, loadCollections]);

  const refreshAll = useCallback(async () => {
    const jobs = [loadSummary(), loadDebtors()];
    if (showCollections) {
      jobs.push(loadCollections(collectionDate));
    }
    await Promise.all(jobs);
    dispatchNavBadgesRefresh();
  }, [loadSummary, loadDebtors, showCollections, collectionDate, loadCollections]);

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
          subtext="Tap to see who paid"
          tone={Number(summary.collected_today) > 0 ? 'success' : 'default'}
          onClick={() => {
            setCollectionDate(getTodayDateString());
            setShowCollections(true);
          }}
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

      {showCollections ? (
        <section
          className="rounded-lg border bg-card p-4 shadow-sm"
          aria-labelledby="debt-collections-heading"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="debt-collections-heading" className="text-base font-semibold">
                Collections
              </h2>
              <p className="text-sm text-muted-foreground">
                Who paid and how much on {formatDateLabel(collectionDate)}.
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowCollections(false)}
              aria-label="Close collections"
            >
              <X className="h-4 w-4" />
              Close
            </Button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCollectionDate((prev) => shiftDate(prev, -1))}
              aria-label="Previous day"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Input
              type="date"
              value={collectionDate}
              onChange={(e) => setCollectionDate(e.target.value || getTodayDateString())}
              className="h-9 w-[11.5rem]"
              aria-label="Collection date"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCollectionDate((prev) => shiftDate(prev, 1))}
              disabled={collectionDate >= getTodayDateString()}
              aria-label="Next day"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            {collectionDate !== getTodayDateString() ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCollectionDate(getTodayDateString())}
              >
                Today
              </Button>
            ) : null}
            <p className="ml-auto text-sm font-medium tabular-nums">
              {collections.count} payment{collections.count === 1 ? '' : 's'} ·{' '}
              {formatCurrency(collections.total)}
            </p>
          </div>

          {collectionsLoading ? (
            <div className="mt-4">
              <PageLoading rows={4} />
            </div>
          ) : collections.results.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                icon={Banknote}
                title="No collections on this day"
                description="Debt payments recorded here will list the customer and amount."
              />
            </div>
          ) : (
            <div className="mt-4">
              <DataTable>
                <DataTableHeader>
                  <DataTableHead>Time</DataTableHead>
                  <DataTableHead>Customer</DataTableHead>
                  <DataTableHead align="right">Amount paid</DataTableHead>
                  <DataTableHead align="right">Balance after</DataTableHead>
                  <DataTableHead>Received by</DataTableHead>
                  <DataTableHead>Notes</DataTableHead>
                </DataTableHeader>
                <DataTableBody>
                  {collections.results.map((row) => {
                    const remaining = Number(row.balance_after);
                    const stillOwes = !Number.isNaN(remaining) && remaining < 0;
                    return (
                      <DataTableRow key={row.id}>
                        <DataTableCell className="whitespace-nowrap text-sm text-muted-foreground">
                          {row.created_at ? formatDateTime(row.created_at) : '—'}
                        </DataTableCell>
                        <DataTableCell>
                          <Link
                            to={customerDetailPath(row.customer_id, { tab: 'ledger' })}
                            className="font-medium hover:underline"
                          >
                            {row.customer_name || 'Customer'}
                          </Link>
                          <div className="text-xs text-muted-foreground">
                            {[row.customer_phone, row.customer_code].filter(Boolean).join(' · ') ||
                              '—'}
                          </div>
                        </DataTableCell>
                        <DataTableCell align="right" className="font-semibold text-success">
                          {formatCurrency(row.amount)}
                        </DataTableCell>
                        <DataTableCell
                          align="right"
                          className={
                            stillOwes
                              ? 'text-sm text-destructive'
                              : 'text-sm text-muted-foreground'
                          }
                        >
                          {stillOwes ? formatCurrency(Math.abs(remaining)) : 'Settled'}
                        </DataTableCell>
                        <DataTableCell className="text-sm text-muted-foreground">
                          {row.received_by || '—'}
                        </DataTableCell>
                        <DataTableCell className="max-w-[16rem] truncate text-sm text-muted-foreground">
                          {[row.reference, row.notes].filter(Boolean).join(' · ') || '—'}
                        </DataTableCell>
                      </DataTableRow>
                    );
                  })}
                </DataTableBody>
              </DataTable>
            </div>
          )}
        </section>
      ) : null}

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
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          navigate(customerDetailPath(row.id, { tab: 'ledger' }))
                        }
                      >
                        <History className="mr-1 h-3.5 w-3.5" />
                        History
                      </Button>
                      <Link
                        to={customerDetailPath(row.id)}
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
    </PageShell>
  );
}
