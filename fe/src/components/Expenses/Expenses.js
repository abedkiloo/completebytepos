import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Check, NotebookText, Pencil, Plus, RefreshCw, Trash2, TrendingDown, X } from 'lucide-react';
import { expensesAPI } from '../../services/api';
import { CATALOG_FETCH_PAGE_SIZE, DEFAULT_PAGE_SIZE } from '../../config/pagination';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import ExpenseForm from './ExpenseForm';
import PeriodPills from '../Reports/PeriodPills';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { formatOccurredDate } from '../../utils/localDate';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  canApproveFinancialRecord,
  canEditExpense,
  getPermissionsFromStorage,
  isMakerCheckerEnabled,
} from '../../utils/makerChecker';
import {
  buildExpenseFilterParams,
  buildExpenseListParams,
  normalizeFilterChangeValue,
} from '../../utils/expenseFilters';
import {
  DEFAULT_REPORT_PERIOD,
  REPORT_PERIODS,
  detectPeriodFromDates,
  periodToDateFilters,
} from '../../utils/reportPeriods';
import { rejectionReturnedMessage } from '../../utils/approvalReturn';
import HelpHint from '../Shared/HelpHint';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
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
  StatusBadge,
  ListPaginationRail,
} from '../page';
import { useListOrdering } from '../../hooks/useListOrdering';

function filtersFromSearchParams(searchParams) {
  const defaults = periodToDateFilters(DEFAULT_REPORT_PERIOD);
  const date_from = searchParams.get('date_from') || defaults.date_from;
  const date_to = searchParams.get('date_to') || defaults.date_to;
  return {
    category: searchParams.get('category') || '',
    status: searchParams.get('status') || '',
    date_from,
    date_to,
    payment_method: searchParams.get('payment_method') || '',
    include_in_trading_profit: searchParams.get('include_in_trading_profit') || '',
    search: searchParams.get('search') || '',
  };
}

const Expenses = () => {
  const [searchParams] = useSearchParams();
  const [expenses, setExpenses] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [notesExpense, setNotesExpense] = useState(null);
  const [totals, setTotals] = useState({
    total_amount: 0,
    expense_count: 0,
    posted_total: 0,
  });
  const [totalsError, setTotalsError] = useState('');
  const [filters, setFilters] = useState(() => filtersFromSearchParams(searchParams));
  const [period, setPeriod] = useState(() => {
    const initial = filtersFromSearchParams(searchParams);
    return detectPeriodFromDates(initial.date_from, initial.date_to);
  });
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });
  const { ordering, setOrdering } = useListOrdering();
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const permissions = getPermissionsFromStorage();

  useEffect(() => {
    loadCategories();
  }, []);

  // Deep-link from trading profit (or bookmarks): apply date/status from the URL.
  useEffect(() => {
    const hasDeepLink =
      searchParams.has('date_from') ||
      searchParams.has('date_to') ||
      searchParams.has('status') ||
      searchParams.has('include_in_trading_profit');
    if (!hasDeepLink) return;
    const next = filtersFromSearchParams(searchParams);
    setFilters((prev) => {
      if (
        prev.date_from === next.date_from &&
        prev.date_to === next.date_to &&
        prev.status === next.status &&
        prev.category === next.category &&
        prev.payment_method === next.payment_method &&
        prev.include_in_trading_profit === next.include_in_trading_profit &&
        prev.search === next.search
      ) {
        return prev;
      }
      return next;
    });
    setPeriod(detectPeriodFromDates(next.date_from, next.date_to));
    setPagination((prev) => ({ ...prev, page: 1 }));
  }, [searchParams]);

  const loadCategories = async () => {
    try {
      const response = await expensesAPI.categories.list({
        is_active: 'true',
        page_size: CATALOG_FETCH_PAGE_SIZE,
      });
      const data = response.data.results || response.data || [];
      setCategories(Array.isArray(data) ? data : []);
    } catch (error) {
      setCategories([]);
      toast.error('Failed to load expense categories');
    }
  };

  const loadExpenses = useCallback(async () => {
    setLoading(true);
    setTotalsError('');
    try {
      const params = buildExpenseListParams({
        filters,
        page: pagination.page,
        pageSize: pagination.page_size,
        ordering,
      });
      const statsParams = buildExpenseFilterParams(filters);

      const [listRes, statsOutcome] = await Promise.all([
        expensesAPI.list(params),
        expensesAPI.statistics(statsParams).then(
          (res) => ({ ok: true, res }),
          (err) => ({ ok: false, err })
        ),
      ]);
      const data = listRes.data;

      if (data.results) {
        setExpenses(data.results);
        setPagination((prev) => ({
          ...prev,
          count: data.count || 0,
        }));
      } else {
        setExpenses(Array.isArray(data) ? data : []);
      }

      if (statsOutcome.ok && statsOutcome.res?.data) {
        setTotals({
          total_amount: Number(statsOutcome.res.data.total_amount) || 0,
          expense_count: Number(statsOutcome.res.data.expense_count) || 0,
          posted_total: Number(statsOutcome.res.data.posted_total) || 0,
        });
      } else {
        setTotalsError('Could not load expense totals for this filter.');
      }
    } catch (error) {
      setExpenses([]);
      toast.error('Failed to load expenses');
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.page_size, ordering]);

  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    const next = normalizeFilterChangeValue(value);
    setFilters((prev) => {
      const updated = { ...prev, [name]: next };
      if (name === 'date_from' || name === 'date_to') {
        setPeriod(detectPeriodFromDates(updated.date_from, updated.date_to));
      }
      return updated;
    });
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const handlePeriodChange = (nextPeriod) => {
    const dates = periodToDateFilters(nextPeriod);
    setPeriod(nextPeriod);
    setFilters((prev) => ({
      ...prev,
      date_from: dates.date_from,
      date_to: dates.date_to,
    }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const handleAdd = () => {
    setEditingExpense(null);
    setShowForm(true);
  };

  const handleEdit = (expense) => {
    setEditingExpense(expense);
    setShowForm(true);
  };

  const handleDelete = (id) => {
    setConfirmDelete(id);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    const expense = expenses.find((row) => row.id === confirmDelete);
    const posted = expense && ['approved', 'paid'].includes(expense.status);

    try {
      if (posted) {
        await expensesAPI.void(confirmDelete, {
          reason: 'Corrected — journals reversed so books stay balanced',
        });
        toast.success('Expense voided. Journals reversed so the books stay balanced.');
      } else {
        await expensesAPI.delete(confirmDelete);
        toast.success('Expense deleted successfully');
      }
      loadExpenses();
    } catch (error) {
      toast.error(
        'Failed to correct expense: ' + (error.response?.data?.error || error.message)
      );
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleApprove = async (id) => {
    try {
      await expensesAPI.approve(id);
      loadExpenses();
      toast.success('Expense approved successfully');
    } catch (error) {
      toast.error('Failed to approve expense: ' + (error.response?.data?.error || error.response?.data?.detail || error.message));
    }
  };

  const handleReject = async (id) => {
    const reason = window.prompt('Why are you returning this expense to the person who submitted it?');
    if (!reason || !reason.trim()) return;
    try {
      await expensesAPI.reject(id, { rejection_reason: reason.trim() });
      loadExpenses();
      toast.success(rejectionReturnedMessage('expense'));
    } catch (error) {
      toast.error('Could not return this expense: ' + (error.response?.data?.error || error.response?.data?.detail || error.message));
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingExpense(null);
  };

  const handleFormSave = () => {
    handleFormClose();
    loadExpenses();
  };

  const handleCategoryCreated = (newCategory) => {
    if (newCategory?.id) {
      setCategories((prev) => {
        const without = prev.filter((c) => c.id !== newCategory.id);
        return [...without, newCategory].sort((a, b) =>
          String(a.name).localeCompare(String(b.name))
        );
      });
    } else {
      loadCategories();
    }
  };

  const rangeLabel =
    filters.date_from && filters.date_to
      ? `${filters.date_from} → ${filters.date_to}`
      : 'selected dates';

  return (
    <PageShell>
        <PageHeader
          title="Expenses"
          description={
            makerCheckerOn
              ? 'Track spending. New expenses need checker approval before they affect reports.'
              : 'Track spending, approvals, and payments. Each expense stores the date it occurred.'
          }
        >
          <Button variant="outline" onClick={() => loadCategories()}>
            <RefreshCw className="h-4 w-4" />
            Refresh categories
          </Button>
          <Link to="/expenses/categories">
            <Button type="button" variant="outline">
              Manage categories
            </Button>
          </Link>
          <Button onClick={handleAdd}>
            <Plus className="h-4 w-4" />
            Add expense
          </Button>
        </PageHeader>

        {categories.length === 0 && (
          <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-foreground">
            <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <p>
              No expense categories yet. Add an expense to create one, or run{' '}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                python manage.py init_expense_categories
              </code>
            </p>
          </div>
        )}

        <div className="mb-3 flex flex-wrap items-center gap-3">
          <PeriodPills
            value={period === 'custom' ? null : period}
            onChange={handlePeriodChange}
            size="default"
            periods={REPORT_PERIODS}
          />
        </div>

        <div
          className="mb-4 flex flex-col gap-3 rounded-lg border border-destructive/20 bg-destructive/[0.04] p-4 sm:flex-row sm:items-center sm:justify-between"
          data-testid="expenses-total-banner"
        >
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-destructive/80">
              Total expenses · {rangeLabel}
            </p>
            <p className="text-2xl font-semibold tabular-nums tracking-tight text-destructive">
              {loading && expenses.length === 0 ? '…' : formatCurrency(totals.total_amount)}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {totals.expense_count.toLocaleString()} expense
              {totals.expense_count === 1 ? '' : 's'}
              {' · '}
              Approved / paid {formatCurrency(totals.posted_total)}
            </p>
            {totalsError ? (
              <p className="mt-1 text-xs text-destructive">{totalsError}</p>
            ) : null}
          </div>
          <div className="grid w-full gap-2 sm:w-auto sm:min-w-[16rem] sm:grid-cols-1">
            <SummaryCard
              icon={TrendingDown}
              label="All statuses"
              value={formatCurrency(totals.total_amount)}
              subtext="Matches your filters"
              tone="destructive"
            />
          </div>
        </div>

        <FilterBar>
          <FilterField label="Category">
            <SearchableSelect
              name="category"
              value={filters.category}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All Categories' },
                ...categories.map(cat => ({ id: cat.id, name: cat.name }))
              ]}
              placeholder="All categories"
            />
          </FilterField>
          <FilterField label="Status">
            <SearchableSelect
              name="status"
              value={filters.status}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All Status' },
                { id: 'pending', name: 'Pending' },
                { id: 'approved', name: 'Approved' },
                { id: 'rejected', name: 'Rejected' },
                { id: 'paid', name: 'Paid' }
              ]}
              placeholder="All status"
            />
          </FilterField>
          <FilterField label="Occurred from">
            <Input
              type="date"
              name="date_from"
              value={filters.date_from}
              onChange={handleFilterChange}
            />
          </FilterField>
          <FilterField label="Occurred to">
            <Input
              type="date"
              name="date_to"
              value={filters.date_to}
              onChange={handleFilterChange}
            />
          </FilterField>
          <FilterField label="Payment">
            <SearchableSelect
              name="payment_method"
              value={filters.payment_method}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All Methods' },
                { id: 'cash', name: 'Cash' },
                { id: 'mpesa', name: 'M-PESA' },
                { id: 'bank', name: 'Bank Transfer' },
                { id: 'card', name: 'Card' },
                { id: 'other', name: 'Other' }
              ]}
              placeholder="All methods"
            />
          </FilterField>
          <FilterField label="Trading profit">
            <SearchableSelect
              name="include_in_trading_profit"
              value={filters.include_in_trading_profit}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All expenses' },
                { id: 'true', name: 'Counted in trading profit' },
                { id: 'false', name: 'Excluded from trading profit' },
              ]}
              placeholder="Trading profit"
            />
          </FilterField>
          <FilterField label="Search" className="min-w-[180px] flex-[2]">
            <Input
              type="search"
              name="search"
              placeholder="Search expenses…"
              value={filters.search}
              onChange={handleFilterChange}
            />
          </FilterField>
        </FilterBar>

        {loading && expenses.length === 0 ? (
          <PageLoading rows={6} />
        ) : expenses.length === 0 ? (
          <EmptyState
            icon={TrendingDown}
            title="No expenses found"
            description="Adjust filters or record your first expense, including the date it occurred. The total above still reflects this date range."
            actionLabel="Add expense"
            onAction={handleAdd}
          />
        ) : (
          <ListPaginationRail
            page={pagination.page}
            pageSize={pagination.page_size}
            totalCount={pagination.count}
            ordering={ordering}
            onOrderingChange={setOrdering}
            onPageChange={(nextPage) =>
              setPagination((prev) => ({ ...prev, page: nextPage }))
            }
          >
            <DataTable>
              <DataTableHeader>
                <DataTableHead>#</DataTableHead>
                <DataTableHead sortKey="saved" ordering={ordering} onOrderingChange={setOrdering}>
                  Date occurred
                </DataTableHead>
                <DataTableHead>Category</DataTableHead>
                <DataTableHead sortKey="name" ordering={ordering} onOrderingChange={setOrdering}>
                  Description
                </DataTableHead>
                <DataTableHead align="right">Amount</DataTableHead>
                <DataTableHead>Status</DataTableHead>
                <DataTableHead>Trading profit</DataTableHead>
                <DataTableHead>Notes</DataTableHead>
                <DataTableHead align="right">Actions</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {expenses.map((expense) => {
                  const hasNotes = Boolean(String(expense.notes || '').trim());
                  return (
                  <DataTableRow key={expense.id}>
                    <DataTableCell className="font-medium">
                      {expense.expense_number}
                    </DataTableCell>
                    <DataTableCell className="text-muted-foreground whitespace-nowrap">
                      {formatOccurredDate(expense.expense_date) || formatDate(expense.expense_date)}
                    </DataTableCell>
                    <DataTableCell>{expense.category_name || '—'}</DataTableCell>
                    <DataTableCell className="max-w-[200px] truncate">
                      {expense.description}
                    </DataTableCell>
                    <DataTableCell align="right" className="font-semibold">
                      {formatCurrency(expense.amount)}
                    </DataTableCell>
                    <DataTableCell>
                      <StatusBadge status={expense.status} />
                    </DataTableCell>
                    <DataTableCell className="text-xs text-muted-foreground whitespace-nowrap">
                      {expense.include_in_trading_profit === false ? 'Excluded' : 'Included'}
                    </DataTableCell>
                    <DataTableCell>
                      {hasNotes ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="max-w-[160px] gap-1.5"
                          onClick={() => setNotesExpense(expense)}
                          title="View notes"
                          aria-label={`View notes for ${expense.expense_number || 'expense'}`}
                        >
                          <NotebookText className="h-4 w-4 shrink-0 text-primary" />
                          <span className="truncate text-xs">View notes</span>
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </DataTableCell>
                    <DataTableCell align="right">
                      <div className="flex justify-end gap-1">
                        {expense.status === 'pending' &&
                          canApproveFinancialRecord(
                            expense,
                            storeSettings,
                            undefined,
                            'expenses',
                          ) && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApprove(expense.id)}
                              title="Approve"
                            >
                              <Check className="h-4 w-4 text-success" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleReject(expense.id)}
                              title="Return to requester"
                            >
                              <X className="h-4 w-4 text-destructive" />
                            </Button>
                            <HelpHint actionKey="reject_change" />
                          </>
                        )}
                        {canEditExpense(expense, storeSettings, permissions) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(expense)}
                          aria-label="Edit expense"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        )}
                        {expense.status !== 'voided' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => handleDelete(expense.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                        )}
                      </div>
                    </DataTableCell>
                  </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </ListPaginationRail>
        )}

        {showForm && (
          <ExpenseForm
            expense={editingExpense}
            categories={categories}
            onClose={handleFormClose}
            onSave={handleFormSave}
            onCategoryCreated={handleCategoryCreated}
          />
        )}

      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Correct expense"
        message="Posted expenses are voided (not erased) and journals are reversed so cash and P&L stay balanced. Continue?"
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Void / correct"
        cancelText="Cancel"
        type="danger"
      />

      <Dialog
        open={!!notesExpense}
        onOpenChange={(open) => {
          if (!open) setNotesExpense(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Expense notes</DialogTitle>
            <DialogDescription>
              {notesExpense
                ? `${notesExpense.expense_number || 'Expense'} · ${notesExpense.description || ''}`
                : 'Full notes for this expense.'}
            </DialogDescription>
          </DialogHeader>
          <div className="reminder-banner max-h-[50vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">
            {String(notesExpense?.notes || '').trim() || 'No notes.'}
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setNotesExpense(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </PageShell>
  );
};

export default Expenses;
