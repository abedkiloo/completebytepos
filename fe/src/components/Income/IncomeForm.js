import React, { useState, useEffect } from 'react';
import { incomeAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import './Income.css';

const IncomeForm = ({ income, categories, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    category: '',
    amount: '',
    description: '',
    payment_method: 'cash',
    payer: '',
    reference_number: '',
    income_date: new Date().toISOString().split('T')[0],
    notes: '',
    status: 'pending',
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (income) {
      setFormData({
        category: income.category || '',
        amount: income.amount || '',
        description: income.description || '',
        payment_method: income.payment_method || 'cash',
        payer: income.payer || '',
        reference_number: income.reference_number || '',
        income_date: income.income_date || new Date().toISOString().split('T')[0],
        notes: income.notes || '',
        status: income.status || 'pending',
      });
    }
  }, [income]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
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
    if (!formData.income_date) {
      newErrors.income_date = 'Income date is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }
    
    setLoading(true);
    try {
      if (income) {
        await incomeAPI.update(income.id, formData);
      } else {
        await incomeAPI.create(formData);
      }
      onSave();
    } catch (error) {
      const errorData = error.response?.data;
      if (errorData) {
        setErrors(errorData);
      } else {
        toast.error('Failed to save income: ' + error.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content income-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{income ? 'Edit Income' : 'Add New Income'}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label>Category *</label>
              <select
                name="category"
                value={formData.category}
                onChange={handleChange}
                className={errors.category ? 'error' : ''}
              >
                <option value="">Select Category</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              {errors.category && <span className="error-text">{errors.category}</span>}
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
              <label>Income Date *</label>
              <input
                type="date"
                name="income_date"
                value={formData.income_date}
                onChange={handleChange}
                className={errors.income_date ? 'error' : ''}
                required
              />
              {errors.income_date && <span className="error-text">{errors.income_date}</span>}
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
              <label>Payer</label>
              <input
                type="text"
                name="payer"
                value={formData.payer}
                onChange={handleChange}
                placeholder="Payer name"
              />
            </div>

            <div className="form-group">
              <label>Reference Number</label>
              <input
                type="text"
                name="reference_number"
                value={formData.reference_number}
                onChange={handleChange}
                placeholder="Reference number"
              />
            </div>

            {income && (
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
                  <option value="received">Received</option>
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

          <div className="modal-footer">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading}>
              {loading ? 'Saving...' : income ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default IncomeForm;

