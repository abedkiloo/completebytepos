import React, { useState, useEffect, useCallback } from 'react';
import { Check, Pencil, Plus, RefreshCw, Trash2, TrendingDown } from 'lucide-react';
import { expensesAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  canApproveFinancialRecord,
  isMakerCheckerEnabled,
} from '../../utils/makerChecker';
import ExpenseForm from './ExpenseForm';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
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
  StatusBadge,
} from '../page';

const Expenses = () => {
  const [expenses, setExpenses] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [filters, setFilters] = useState({
    category: '',
    status: '',
    date_from: '',
    date_to: '',
    payment_method: '',
    search: '',
  });
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      const response = await expensesAPI.categories.list({ is_active: 'true' });
      const data = response.data.results || response.data || [];
      setCategories(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadExpenses = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: pagination.page,
        page_size: pagination.page_size,
      };
      
      if (filters.category) params.category = filters.category;
      if (filters.status) params.status = filters.status;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.payment_method) params.payment_method = filters.payment_method;
      if (filters.search) params.search = filters.search;
      
      const response = await expensesAPI.list(params);
      const data = response.data;
      
      if (data.results) {
        setExpenses(data.results);
        setPagination(prev => ({
          ...prev,
          count: data.count || 0,
        }));
      } else {
        setExpenses(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Error loading expenses:', error);
      setExpenses([]);
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.page_size]);

  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
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
    
    try {
      await expensesAPI.delete(confirmDelete);
      loadExpenses();
      toast.success('Expense deleted successfully');
    } catch (error) {
      toast.error('Failed to delete expense: ' + (error.response?.data?.error || error.message));
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
      toast.error('Failed to approve expense: ' + (error.response?.data?.error || error.message));
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
    // Reload categories to include the new one
    loadCategories();
  };

  const totalPages = Math.ceil(pagination.count / pagination.page_size) || 1;

  if (loading && expenses.length === 0) {
    return (
      <PageLoading rows={8} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Expenses"
          description={
            makerCheckerOn
              ? 'Track spending. New expenses need checker approval before they affect reports.'
              : 'Track spending, approvals, and payments.'
          }
        >
          <Button variant="outline" onClick={() => loadCategories()}>
            <RefreshCw className="h-4 w-4" />
            Refresh categories
          </Button>
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
          <FilterField label="From">
            <Input
              type="date"
              name="date_from"
              value={filters.date_from}
              onChange={handleFilterChange}
            />
          </FilterField>
          <FilterField label="To">
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

        {expenses.length === 0 ? (
          <EmptyState
            icon={TrendingDown}
            title="No expenses found"
            description="Adjust filters or record your first expense."
            actionLabel="Add expense"
            onAction={handleAdd}
          />
        ) : (
          <>
            <DataTable>
              <DataTableHeader>
                <DataTableHead>#</DataTableHead>
                <DataTableHead>Date</DataTableHead>
                <DataTableHead>Category</DataTableHead>
                <DataTableHead>Description</DataTableHead>
                <DataTableHead align="right">Amount</DataTableHead>
                <DataTableHead>Status</DataTableHead>
                <DataTableHead align="right">Actions</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {expenses.map((expense) => (
                  <DataTableRow key={expense.id}>
                    <DataTableCell className="font-medium">
                      {expense.expense_number}
                    </DataTableCell>
                    <DataTableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDate(expense.expense_date)}
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
                    <DataTableCell align="right">
                      <div className="flex justify-end gap-1">
                        {expense.status === 'pending' &&
                          canApproveFinancialRecord(
                            expense,
                            storeSettings,
                            undefined,
                            'expenses',
                          ) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleApprove(expense.id)}
                            title="Approve"
                          >
                            <Check className="h-4 w-4 text-success" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(expense)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => handleDelete(expense.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </DataTableCell>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>

            {pagination.count > pagination.page_size && (
              <div className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Page {pagination.page} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.page === 1}
                    onClick={() =>
                      setPagination((prev) => ({ ...prev, page: prev.page - 1 }))
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.page >= totalPages}
                    onClick={() =>
                      setPagination((prev) => ({ ...prev, page: prev.page + 1 }))
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Expense Form Modal */}
        {showForm && (
          <ExpenseForm
            expense={editingExpense}
            categories={categories}
            onClose={handleFormClose}
            onSave={handleFormSave}
            onCategoryCreated={handleCategoryCreated}
          />
        )}

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete Expense"
        message="Are you sure you want to delete this expense?"
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
      </PageShell>
  );
};

export default Expenses;

