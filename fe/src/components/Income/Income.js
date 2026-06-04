import React, { useState, useEffect, useCallback } from 'react';
import { Check, Pencil, Plus, Trash2, TrendingUp } from 'lucide-react';
import { incomeAPI } from '../../services/api';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  canApproveFinancialRecord,
  isMakerCheckerEnabled,
} from '../../utils/makerChecker';
import IncomeForm from './IncomeForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
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

const Income = () => {
  const [incomes, setIncomes] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingIncome, setEditingIncome] = useState(null);
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
    page_size: 20,
    count: 0,
  });
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      const response = await incomeAPI.categories.list({ is_active: 'true' });
      const data = response.data.results || response.data || [];
      setCategories(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const loadIncomes = useCallback(async () => {
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
      
      const response = await incomeAPI.list(params);
      const data = response.data;
      
      if (data.results) {
        setIncomes(data.results);
        setPagination(prev => ({
          ...prev,
          count: data.count || 0,
        }));
      } else {
        setIncomes(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Error loading incomes:', error);
      setIncomes([]);
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.page_size]);

  useEffect(() => {
    loadIncomes();
  }, [loadIncomes]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleAdd = () => {
    setEditingIncome(null);
    setShowForm(true);
  };

  const handleEdit = (income) => {
    setEditingIncome(income);
    setShowForm(true);
  };

  const handleDelete = (id) => {
    setConfirmDelete(id);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    
    try {
      await incomeAPI.delete(confirmDelete);
      loadIncomes();
      toast.success('Income deleted successfully');
    } catch (error) {
      toast.error('Failed to delete income: ' + (error.response?.data?.error || error.message));
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleApprove = async (id) => {
    try {
      await incomeAPI.approve(id);
      loadIncomes();
      toast.success('Income approved successfully');
    } catch (error) {
      toast.error('Failed to approve income: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingIncome(null);
  };

  const handleFormSave = () => {
    handleFormClose();
    loadIncomes();
  };

  const totalPages = Math.ceil(pagination.count / pagination.page_size) || 1;

  if (loading && incomes.length === 0) {
    return (
      <PageLoading rows={8} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Income"
          description={
            makerCheckerOn
              ? 'Track non-sales revenue. New income needs checker approval before it affects reports.'
              : 'Track non-sales revenue and receipts.'
          }
        >
          <Button onClick={handleAdd}>
            <Plus className="h-4 w-4" />
            Add income
          </Button>
        </PageHeader>

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
                { id: 'received', name: 'Received' }
              ]}
              placeholder="All status"
            />
          </FilterField>
          <FilterField label="From">
            <Input type="date" name="date_from" value={filters.date_from} onChange={handleFilterChange} />
          </FilterField>
          <FilterField label="To">
            <Input type="date" name="date_to" value={filters.date_to} onChange={handleFilterChange} />
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
              placeholder="Search income…"
              value={filters.search}
              onChange={handleFilterChange}
            />
          </FilterField>
        </FilterBar>

        {incomes.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="No income records"
            description="Add income to track money coming in outside of POS sales."
            actionLabel="Add income"
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
                {incomes.map((income) => (
                  <DataTableRow key={income.id}>
                    <DataTableCell className="font-medium">{income.income_number}</DataTableCell>
                    <DataTableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDate(income.income_date)}
                    </DataTableCell>
                    <DataTableCell>{income.category_name || '—'}</DataTableCell>
                    <DataTableCell className="max-w-[200px] truncate">
                      {income.description}
                    </DataTableCell>
                    <DataTableCell align="right" className="font-semibold">
                      {formatCurrency(income.amount)}
                    </DataTableCell>
                    <DataTableCell>
                      <StatusBadge status={income.status} />
                    </DataTableCell>
                    <DataTableCell align="right">
                      <div className="flex justify-end gap-1">
                        {income.status === 'pending' &&
                          canApproveFinancialRecord(
                            income,
                            storeSettings,
                            undefined,
                            'income',
                          ) && (
                          <Button variant="ghost" size="sm" onClick={() => handleApprove(income.id)}>
                            <Check className="h-4 w-4 text-success" />
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(income)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => handleDelete(income.id)}
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
                    onClick={() => setPagination((p) => ({ ...p, page: p.page - 1 }))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.page >= totalPages}
                    onClick={() => setPagination((p) => ({ ...p, page: p.page + 1 }))}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Income Form Modal */}
        {showForm && (
          <IncomeForm
            income={editingIncome}
            categories={categories}
            onClose={handleFormClose}
            onSave={handleFormSave}
          />
        )}

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete Income"
        message="Are you sure you want to delete this income?"
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
      </PageShell>
  );
};

export default Income;

