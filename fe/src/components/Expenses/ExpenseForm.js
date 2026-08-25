import React, { useState, useEffect } from 'react';
import { expensesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import CommitConfirm from '../Shared/CommitConfirm';
import { formatCurrency } from '../../utils/formatters';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  financialSubmitSuccessMessage,
  isMakerCheckerEnabled,
} from '../../utils/makerChecker';
import { findCategoryByName } from '../../utils/expenseFilters';
import { CATALOG_FETCH_PAGE_SIZE } from '../../config/pagination';

const ExpenseForm = ({ expense, categories, onClose, onSave, onCategoryCreated }) => {
  const [formData, setFormData] = useState({
    category: '',
    amount: '',
    description: '',
    payment_method: 'cash',
    vendor: '',
    receipt_number: '',
    expense_date: new Date().toISOString().split('T')[0],
    notes: '',
    status: 'pending',
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [newCategory, setNewCategory] = useState({ name: '', description: '' });
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [proposalReason, setProposalReason] = useState('');
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  useEffect(() => {
    if (expense) {
      setFormData({
        category: expense.category || '',
        amount: expense.amount || '',
        description: expense.description || '',
        payment_method: expense.payment_method || 'cash',
        vendor: expense.vendor || '',
        receipt_number: expense.receipt_number || '',
        expense_date: expense.expense_date || new Date().toISOString().split('T')[0],
        notes: expense.notes || '',
        status: expense.status || 'pending',
      });
    }
  }, [expense]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.category) {
      newErrors.category = 'Category is required';
    }
    if (!formData.amount || parseFloat(formData.amount) <= 0) {
      newErrors.amount = 'Amount must be greater than 0';
    }
    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }
    if (!formData.expense_date) {
      newErrors.expense_date = 'Expense date is required';
    }
    if (makerCheckerOn && !proposalReason.trim()) {
      newErrors.proposal_reason = 'A reason is required when maker-checker is enabled.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const selectCategory = (category) => {
    if (!category?.id) return;
    setFormData((prev) => ({ ...prev, category: category.id }));
    setNewCategory({ name: '', description: '' });
    setShowCategoryForm(false);
    if (onCategoryCreated) {
      onCategoryCreated(category);
    }
  };

  const resolveExistingCategory = async (name) => {
    const local = findCategoryByName(categories, name);
    if (local) return local;
    try {
      const response = await expensesAPI.categories.list({
        search: name,
        page_size: CATALOG_FETCH_PAGE_SIZE,
      });
      const rows = response.data.results || response.data || [];
      return findCategoryByName(Array.isArray(rows) ? rows : [], name);
    } catch {
      return null;
    }
  };

  const handleCreateCategory = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!newCategory.name.trim()) {
      toast.error('Category name is required');
      return;
    }

    setCreatingCategory(true);
    try {
      const response = await expensesAPI.categories.create(newCategory);
      const created = response.data;
      if (response.status === 200) {
        toast.success(`Using existing category “${created.name}”`);
      } else {
        toast.success('Category created successfully');
      }
      selectCategory(created);
    } catch (error) {
      const errorData = error.response?.data;
      const nameError = errorData?.name?.[0] || '';
      if (/already exists/i.test(nameError)) {
        const existing = await resolveExistingCategory(newCategory.name);
        if (existing) {
          toast.success(`Using existing category “${existing.name}”`);
          selectCategory(existing);
          return;
        }
      }
      if (nameError) {
        toast.error(nameError);
      } else {
        toast.error('Failed to create category: ' + (errorData?.detail || error.message));
      }
    } finally {
      setCreatingCategory(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!validate()) {
      return;
    }
    setShowCommitConfirm(true);
  };

  const confirmCommit = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const payload = { ...formData };
      if (makerCheckerOn) {
        payload.proposal_reason = proposalReason.trim();
        payload.status = 'pending';
      }
      if (expense) {
        await expensesAPI.update(expense.id, payload);
      } else {
        await expensesAPI.create(payload);
      }
      const mcMsg = financialSubmitSuccessMessage(storeSettings);
      if (mcMsg) toast.warning(mcMsg);
      else toast.success(expense ? 'Expense updated' : 'Expense created');
      setShowCommitConfirm(false);
      onSave();
    } catch (error) {
      const errorData = error.response?.data;
      if (errorData) {
        setErrors(errorData);
        toast.error(
          errorData.detail ||
            errorData.error ||
            'Failed to save expense. Check the form fields.'
        );
      } else {
        toast.error('Failed to save expense: ' + error.message);
      }
      setShowCommitConfirm(false);
    } finally {
      setLoading(false);
    }
  };

  const categoryName =
    (categories || []).find((c) => Number(c.id) === Number(formData.category))?.name ||
    formData.category ||
    '—';
  const commitRows = [
    { label: 'Category', value: String(categoryName) },
    {
      label: 'Amount',
      value: formatCurrency(formData.amount),
      tone: 'danger',
      emphasis: true,
    },
    formData.description ? { label: 'Description', value: formData.description } : null,
    formData.vendor ? { label: 'Vendor', value: formData.vendor } : null,
    formData.expense_date ? { label: 'Date', value: formData.expense_date } : null,
    { label: 'Method', value: formData.payment_method },
  ].filter(Boolean);


  return (
    <>
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{expense ? 'Edit Expense' : 'Add New Expense'}</h2>
          <button className="slide-in-panel-close" onClick={onClose}>×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label>Category *</label>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                  <SearchableSelect
                    name="category"
                    value={formData.category}
                    onChange={handleChange}
                    options={categories.map(cat => ({ id: cat.id, name: cat.name }))}
                    placeholder="Select Category"
                    className={errors.category ? 'error' : ''}
                    onAddNew={() => setShowCategoryForm(!showCategoryForm)}
                    addNewLabel="+ Add Category"
                  />
                </div>
              </div>
              {errors.category && <span className="error-text">{errors.category}</span>}
              {categories.length === 0 && (
                <div className="info-message" style={{ marginTop: '0.5rem', padding: '0.75rem', background: '#fef3c7', border: '1px solid #fbbf24', borderRadius: '4px', fontSize: '0.875rem' }}>
                  ⚠️ No categories available. Please create a category first.
                </div>
              )}

              {showCategoryForm && (
                <div className="category-form" style={{ marginTop: '1rem', padding: '1rem', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '6px' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', fontWeight: '600' }}>Create New Category</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <input
                      type="text"
                      placeholder="Category name *"
                      value={newCategory.name}
                      onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
                      style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px' }}
                    />
                    <textarea
                      placeholder="Description (optional)"
                      value={newCategory.description}
                      onChange={(e) => setNewCategory({ ...newCategory, description: e.target.value })}
                      rows="2"
                      style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', resize: 'vertical' }}
                    />
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        onClick={() => {
                          setShowCategoryForm(false);
                          setNewCategory({ name: '', description: '' });
                        }}
                        disabled={creatingCategory}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleCreateCategory}
                        disabled={creatingCategory || !newCategory.name.trim()}
                        style={{ background: '#6366f1', color: 'white' }}
                      >
                        {creatingCategory ? 'Creating...' : 'Create'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="form-group">
              <label>Amount *</label>
              <input
                type="number"
                name="amount"
                value={formData.amount}
                onChange={handleChange}
                step="0.01"
                min="0.01"
                className={errors.amount ? 'error' : ''}
                required
              />
              {errors.amount && <span className="error-text">{errors.amount}</span>}
            </div>

            <div className="form-group">
              <label>Expense Date *</label>
              <input
                type="date"
                name="expense_date"
                value={formData.expense_date}
                onChange={handleChange}
                className={errors.expense_date ? 'error' : ''}
                required
              />
              {errors.expense_date && <span className="error-text">{errors.expense_date}</span>}
            </div>

            <div className="form-group">
              <label>Payment Method *</label>
              <SearchableSelect
                name="payment_method"
                value={formData.payment_method}
                onChange={handleChange}
                options={[
                  { id: 'cash', name: 'Cash' },
                  { id: 'mpesa', name: 'M-PESA' },
                  { id: 'bank', name: 'Bank Transfer' },
                  { id: 'card', name: 'Card' },
                  { id: 'other', name: 'Other' }
                ]}
                placeholder="Select Payment Method"
              />
            </div>

            <div className="form-group full-width">
              <label>Description *</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows="3"
                className={errors.description ? 'error' : ''}
                required
              />
              {errors.description && <span className="error-text">{errors.description}</span>}
            </div>

            <div className="form-group">
              <label>Vendor</label>
              <input
                type="text"
                name="vendor"
                value={formData.vendor}
                onChange={handleChange}
                placeholder="Vendor/Supplier name"
              />
            </div>

            <div className="form-group">
              <label>Receipt Number</label>
              <input
                type="text"
                name="receipt_number"
                value={formData.receipt_number}
                onChange={handleChange}
                placeholder="Receipt number"
              />
            </div>

            {makerCheckerOn ? (
              <ChangeReasonField
                context="financial"
                value={proposalReason}
                onChange={setProposalReason}
                error={errors.proposal_reason}
              />
            ) : null}

            {expense && !makerCheckerOn && (
              <div className="form-group">
                <label>Status</label>
                <SearchableSelect
                  name="status"
                  value={formData.status}
                  onChange={handleChange}
                  options={[
                    { id: 'pending', name: 'Pending' },
                    { id: 'approved', name: 'Approved' },
                    { id: 'rejected', name: 'Rejected' },
                    { id: 'paid', name: 'Paid' }
                  ]}
                  placeholder="Select Status"
                />
              </div>
            )}

            <div className="form-group full-width">
              <label>Notes</label>
              <textarea
                name="notes"
                value={formData.notes}
                onChange={handleChange}
                rows="2"
                placeholder="Additional notes..."
              />
            </div>
          </div>
          <div className="slide-in-panel-footer">
            <button type="button" onClick={onClose} disabled={loading} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Saving...' : expense ? 'Update' : 'Create'}
            </button>
          </div>
          </form>
        </div>
      </div>
    </div>
    <CommitConfirm
      open={showCommitConfirm}
      onOpenChange={(open) => {
        if (!open && !loading) setShowCommitConfirm(false);
      }}
      title="Confirm expense?"
      description="Review the expense details, then confirm to save."
      rows={commitRows}
      submitting={loading}
      confirmText={makerCheckerOn ? 'Submit for approval' : (expense ? 'Confirm & update' : 'Confirm & create')}
      onConfirm={confirmCommit}
      variant="warning"
    />
    </>
  );
};

export default ExpenseForm;
