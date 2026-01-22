import React, { useState, useEffect, useCallback } from 'react';
import { incomeAPI } from '../../services/api';
import { formatCurrency, formatDate } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import IncomeForm from './IncomeForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import '../../styles/shared.css';
import './Income.css';

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

  const getStatusBadgeClass = (status) => {
    const classes = {
      'pending': 'pending',
      'approved': 'approved',
      'rejected': 'rejected',
      'received': 'received',
    };
    return classes[status] || 'pending';
  };

  return (
    <Layout>
      <div className="income-page">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Income Management</h1>
            <p>Track and manage business income</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={handleAdd}>
              <span>+</span>
              <span>Add Income</span>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="income-filters">
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
                { id: 'received', name: 'Received' }
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
              placeholder="Search incomes..."
              value={filters.search}
              onChange={handleFilterChange}
            />
          </div>
        </div>

        {/* Incomes Table */}
        <div className="income-table-container">
          {loading ? (
            <div className="loading-state">Loading incomes...</div>
          ) : incomes.length === 0 ? (
            <div className="empty-state">No incomes found</div>
          ) : (
            <>
              <table className="income-table">
                <thead>
                  <tr>
                    <th>Income #</th>
                    <th>Date</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Payer</th>
                    <th>Amount</th>
                    <th>Payment</th>
                    <th>Status</th>
                    <th>Created By</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {incomes.map(income => (
                    <tr key={income.id}>
                      <td className="income-number">{income.income_number}</td>
                      <td>{formatDate(income.income_date)}</td>
                      <td>{income.category_name || 'N/A'}</td>
                      <td className="description-cell">{income.description}</td>
                      <td>{income.payer || 'N/A'}</td>
                      <td className="amount-cell">{formatCurrency(income.amount)}</td>
                      <td>
                        <span className="payment-badge">{income.payment_method}</span>
                      </td>
                      <td>
                        <span className={`status-badge ${getStatusBadgeClass(income.status)}`}>
                          {income.status}
                        </span>
                      </td>
                      <td>{income.created_by_name || 'N/A'}</td>
                      <td>
                        <div className="action-buttons">
                          {income.status === 'pending' && (
                            <button
                              className="btn-approve"
                              onClick={() => handleApprove(income.id)}
                              title="Approve"
                            >
                              ✓
                            </button>
                          )}
                          <button
                            className="btn-edit"
                            onClick={() => handleEdit(income)}
                            title="Edit"
                          >
                            ✎
                          </button>
                          <button
                            className="btn-delete"
                            onClick={() => handleDelete(income.id)}
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
      </div>
    </Layout>
  );
};

export default Income;

