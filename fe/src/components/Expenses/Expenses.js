import React, { useState, useEffect, useCallback } from 'react';
import { expensesAPI } from '../../services/api';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDate } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import ExpenseForm from './ExpenseForm';
import '../../styles/shared.css';
import './Expenses.css';

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
    page_size: 20,
    count: 0,
  });

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

  const getStatusBadgeClass = (status) => {
    const classes = {
      'pending': 'pending',
      'approved': 'approved',
      'rejected': 'rejected',
      'paid': 'paid',
    };
    return classes[status] || 'pending';
  };

  return (
    <Layout>
      <div className="expenses-page">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Expenses Management</h1>
            <p>Track and manage business expenses</p>
            {categories.length === 0 && (
              <div className="warning-banner" style={{ marginTop: '0.5rem', padding: '0.75rem', background: '#fef3c7', border: '1px solid #fbbf24', borderRadius: '4px', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>⚠️</span>
                <span>No expense categories available. Click "Add Expense" to create your first category, or run: <code style={{ background: '#f3f4f6', padding: '0.2rem 0.4rem', borderRadius: '3px' }}>python manage.py init_expense_categories</code></span>
              </div>
            )}
          </div>
          <div className="page-header-actions">
            <button className="btn btn-secondary" onClick={() => loadCategories()} title="Refresh Categories">
              <span>🔄</span>
              <span>Categories</span>
            </button>
            <button className="btn btn-primary" onClick={handleAdd}>
              <span>+</span>
              <span>Add Expense</span>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="expenses-filters">
          <div className="filter-group">
            <label>Category</label>
            <SearchableSelect
              name="category"
              value={filters.category}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All Categories' },
                ...categories.map(cat => ({ id: cat.id, name: cat.name }))
              ]}
              placeholder="All Categories"
            />
          </div>
          <div className="filter-group">
            <label>Status</label>
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
              placeholder="All Status"
            />
          </div>
          <div className="filter-group">
            <label>From Date</label>
            <input
              type="date"
              name="date_from"
              value={filters.date_from}
              onChange={handleFilterChange}
            />
          </div>
          <div className="filter-group">
            <label>To Date</label>
            <input
              type="date"
              name="date_to"
              value={filters.date_to}
              onChange={handleFilterChange}
            />
          </div>
          <div className="filter-group">
            <label>Payment Method</label>
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
              placeholder="All Methods"
            />
          </div>
          <div className="filter-group">
            <label>Search</label>
            <input
              type="text"
              name="search"
              placeholder="Search expenses..."
              value={filters.search}
              onChange={handleFilterChange}
            />
          </div>
        </div>

        {/* Expenses Table */}
        <div className="expenses-table-container">
          {loading ? (
            <div className="loading-state">Loading expenses...</div>
          ) : expenses.length === 0 ? (
            <div className="empty-state">No expenses found</div>
          ) : (
            <>
              <table className="expenses-table">
                <thead>
                  <tr>
                    <th>Expense #</th>
                    <th>Date</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Vendor</th>
                    <th>Amount</th>
                    <th>Payment</th>
                    <th>Status</th>
                    <th>Created By</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.map(expense => (
                    <tr key={expense.id}>
                      <td className="expense-number">{expense.expense_number}</td>
                      <td>{formatDate(expense.expense_date)}</td>
                      <td>{expense.category_name || 'N/A'}</td>
                      <td className="description-cell">{expense.description}</td>
                      <td>{expense.vendor || 'N/A'}</td>
                      <td className="amount-cell">{formatCurrency(expense.amount)}</td>
                      <td>
                        <span className="payment-badge">{expense.payment_method}</span>
                      </td>
                      <td>
                        <span className={`status-badge ${getStatusBadgeClass(expense.status)}`}>
                          {expense.status}
                        </span>
                      </td>
                      <td>{expense.created_by_name || 'N/A'}</td>
                      <td>
                        <div className="action-buttons">
                          {expense.status === 'pending' && (
                            <button
                              className="btn-approve"
                              onClick={() => handleApprove(expense.id)}
                              title="Approve"
                            >
                              ✓
                            </button>
                          )}
                          <button
                            className="btn-edit"
                            onClick={() => handleEdit(expense)}
                            title="Edit"
                          >
                            ✎
                          </button>
                          <button
                            className="btn-delete"
                            onClick={() => handleDelete(expense.id)}
                            title="Delete"
                          >
                            ×
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {pagination.count > pagination.page_size && (
                <div className="pagination">
                  <button
                    disabled={pagination.page === 1}
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                  >
                    Previous
                  </button>
                  <span>
                    Page {pagination.page} of {Math.ceil(pagination.count / pagination.page_size)}
                  </span>
                  <button
                    disabled={pagination.page >= Math.ceil(pagination.count / pagination.page_size)}
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

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
      </div>
    </Layout>
  );
};

export default Expenses;

