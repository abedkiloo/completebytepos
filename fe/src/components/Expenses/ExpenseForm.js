import React, { useState, useEffect } from 'react';
import { expensesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import './Expenses.css';

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
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validate = () => {
    const newErrors = {};
    
    if (!formData.amount || parseFloat(formData.amount) <= 0) {
      newErrors.amount = 'Amount must be greater than 0';
    }
    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }
    if (!formData.expense_date) {
      newErrors.expense_date = 'Expense date is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
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
      toast.success('Category created successfully');
      setNewCategory({ name: '', description: '' });
      setShowCategoryForm(false);
      if (onCategoryCreated) {
        onCategoryCreated(response.data);
      }
      // Auto-select the newly created category
      setFormData(prev => ({ ...prev, category: response.data.id }));
    } catch (error) {
      const errorData = error.response?.data;
      if (errorData) {
        if (errorData.name) {
          toast.error(errorData.name[0]);
        } else {
          toast.error('Failed to create category: ' + (errorData.detail || error.message));
        }
      } else {
        toast.error('Failed to create category: ' + error.message);
      }
    } finally {
      setCreatingCategory(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }
    
    setLoading(true);
    try {
      if (expense) {
        await expensesAPI.update(expense.id, formData);
      } else {
        await expensesAPI.create(formData);
      }
      onSave();
    } catch (error) {
      const errorData = error.response?.data;
      if (errorData) {
        setErrors(errorData);
      } else {
        toast.error('Failed to save expense: ' + error.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
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
                <select
                  name="category"
                  value={formData.category}
                  onChange={handleChange}
                  className={errors.category ? 'error' : ''}
                  style={{ flex: 1 }}
                >
                  <option value="">Select Category</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    setShowCategoryForm(!showCategoryForm);
                  }}
                  className="btn-add-category"
                  title="Add New Category"
                >
                  + Add
                </button>
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
              <select
                name="payment_method"
                value={formData.payment_method}
                onChange={handleChange}
                required
              >
                <option value="cash">Cash</option>
                <option value="mpesa">M-PESA</option>
                <option value="bank">Bank Transfer</option>
                <option value="card">Card</option>
                <option value="other">Other</option>
              </select>
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

            {expense && (
              <div className="form-group">
                <label>Status</label>
                <select
                  name="status"
                  value={formData.status}
                  onChange={handleChange}
                >
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="paid">Paid</option>
                </select>
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
  );
};

export default ExpenseForm;

