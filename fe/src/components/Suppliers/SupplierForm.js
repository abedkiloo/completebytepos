import React, { useState, useEffect } from 'react';
import { suppliersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import '../../styles/slide-in-panel.css';
import './Suppliers.css';

const SupplierForm = ({ supplier, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    name: '',
    supplier_type: 'business',
    contact_person: '',
    email: '',
    phone: '',
    alternate_phone: '',
    address: '',
    city: '',
    state: '',
    country: 'Kenya',
    postal_code: '',
    tax_id: '',
    registration_number: '',
    website: '',
    payment_terms: 'net_30',
    credit_limit: '0.00',
    account_balance: '0.00',
    notes: '',
    rating: 5,
    is_preferred: false,
    is_active: true,
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (supplier) {
      setFormData({
        name: supplier.name || '',
        supplier_type: supplier.supplier_type || 'business',
        contact_person: supplier.contact_person || '',
        email: supplier.email || '',
        phone: supplier.phone || '',
        alternate_phone: supplier.alternate_phone || '',
        address: supplier.address || '',
        city: supplier.city || '',
        state: supplier.state || '',
        country: supplier.country || 'Kenya',
        postal_code: supplier.postal_code || '',
        tax_id: supplier.tax_id || '',
        registration_number: supplier.registration_number || '',
        website: supplier.website || '',
        payment_terms: supplier.payment_terms || 'net_30',
        credit_limit: String(supplier.credit_limit || '0.00'),
        account_balance: String(supplier.account_balance || '0.00'),
        notes: supplier.notes || '',
        rating: supplier.rating || 5,
        is_preferred: supplier.is_preferred || false,
        is_active: supplier.is_active !== undefined ? supplier.is_active : true,
      });
    }
  }, [supplier]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
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
    
    if (!formData.name.trim()) {
      newErrors.name = 'Supplier name is required';
    }
    
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }
    
    if (parseFloat(formData.credit_limit) < 0) {
      newErrors.credit_limit = 'Credit limit cannot be negative';
    }
    
    if (parseFloat(formData.account_balance) < 0) {
      newErrors.account_balance = 'Account balance cannot be negative';
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
      const submitData = {
        ...formData,
        credit_limit: parseFloat(formData.credit_limit) || 0,
        account_balance: parseFloat(formData.account_balance) || 0,
        rating: parseInt(formData.rating) || 5,
      };

      let response;
      if (supplier) {
        response = await suppliersAPI.update(supplier.id, submitData);
        toast.success('Supplier updated successfully');
      } else {
        response = await suppliersAPI.create(submitData);
        toast.success('Supplier created successfully');
      }
      
      // Call onSave with the new/updated supplier
      if (onSave) {
        onSave(response.data);
      }
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage = error.response.data.error || 
          Object.values(error.response.data).flat().join(', ') || 
          'Failed to save supplier';
        toast.error(errorMessage);
      } else {
        toast.error('Failed to save supplier: ' + (error.message || 'Unknown error'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{supplier ? 'Edit Supplier' : 'Add Supplier'}</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="supplier-form">
            <div className="form-section">
              <h3>Basic Information</h3>
              <div className="form-row">
                <div className="form-group">
                  <label>Supplier Name *</label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    required
                  />
                  {errors.name && <span className="error">{errors.name}</span>}
                </div>
                <div className="form-group">
                  <label>Supplier Type *</label>
                  <select
                    name="supplier_type"
                    value={formData.supplier_type}
                    onChange={handleChange}
                    required
                  >
                    <option value="individual">Individual</option>
                    <option value="business">Business</option>
                    <option value="manufacturer">Manufacturer</option>
                    <option value="distributor">Distributor</option>
                    <option value="wholesaler">Wholesaler</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="form-section">
              <h3>Contact Information</h3>
              <div className="form-row">
                <div className="form-group">
                  <label>Contact Person</label>
                  <input
                    type="text"
                    name="contact_person"
                    value={formData.contact_person}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label>Email</label>
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                  />
                  {errors.email && <span className="error">{errors.email}</span>}
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Phone</label>
                  <input
                    type="text"
                    name="phone"
                    value={formData.phone}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label>Alternate Phone</label>
                  <input
                    type="text"
                    name="alternate_phone"
                    value={formData.alternate_phone}
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>

            <div className="form-section">
              <h3>Address Information</h3>
              <div className="form-group">
                <label>Address</label>
                <textarea
                  name="address"
                  value={formData.address}
                  onChange={handleChange}
                  rows="2"
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>City</label>
                  <input
                    type="text"
                    name="city"
                    value={formData.city}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label>State/Province</label>
                  <input
                    type="text"
                    name="state"
                    value={formData.state}
                    onChange={handleChange}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Country</label>
                  <input
                    type="text"
                    name="country"
                    value={formData.country}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label>Postal Code</label>
                  <input
                    type="text"
                    name="postal_code"
                    value={formData.postal_code}
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>

            <div className="form-section">
              <h3>Business Information</h3>
              <div className="form-row">
                <div className="form-group">
                  <label>Tax ID / VAT Number</label>
                  <input
                    type="text"
                    name="tax_id"
                    value={formData.tax_id}
                    onChange={handleChange}
                  />
                </div>
                <div className="form-group">
                  <label>Registration Number</label>
                  <input
                    type="text"
                    name="registration_number"
                    value={formData.registration_number}
                    onChange={handleChange}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Website</label>
                <input
                  type="url"
                  name="website"
                  value={formData.website}
                  onChange={handleChange}
                  placeholder="https://example.com"
                />
              </div>
            </div>

            <div className="form-section">
              <h3>Financial Information</h3>
              <div className="form-row">
                <div className="form-group">
                  <label>Payment Terms</label>
                  <select
                    name="payment_terms"
                    value={formData.payment_terms}
                    onChange={handleChange}
                  >
                    <option value="net_15">Net 15</option>
                    <option value="net_30">Net 30</option>
                    <option value="net_45">Net 45</option>
                    <option value="net_60">Net 60</option>
                    <option value="cod">Cash on Delivery</option>
                    <option value="prepaid">Prepaid</option>
                    <option value="custom">Custom Terms</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Credit Limit (KES)</label>
                  <input
                    type="number"
                    name="credit_limit"
                    value={formData.credit_limit}
                    onChange={handleChange}
                    step="0.01"
                    min="0"
                  />
                  {errors.credit_limit && <span className="error">{errors.credit_limit}</span>}
                  <small className="form-text">0 means no credit limit</small>
                </div>
              </div>
              <div className="form-group">
                <label>Account Balance (KES)</label>
                <input
                  type="number"
                  name="account_balance"
                  value={formData.account_balance}
                  onChange={handleChange}
                  step="0.01"
                  min="0"
                />
                {errors.account_balance && <span className="error">{errors.account_balance}</span>}
                <small className="form-text">Amount currently owed to supplier</small>
              </div>
            </div>

            <div className="form-section">
              <h3>Additional Information</h3>
              <div className="form-group">
                <label>Notes</label>
                <textarea
                  name="notes"
                  value={formData.notes}
                  onChange={handleChange}
                  rows="3"
                  placeholder="Additional notes about this supplier"
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Rating (1-5)</label>
                  <select
                    name="rating"
                    value={formData.rating}
                    onChange={handleChange}
                  >
                    <option value="1">1 - Poor</option>
                    <option value="2">2 - Fair</option>
                    <option value="3">3 - Good</option>
                    <option value="4">4 - Very Good</option>
                    <option value="5">5 - Excellent</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="form-checkboxes">
              <label>
                <input
                  type="checkbox"
                  name="is_preferred"
                  checked={formData.is_preferred}
                  onChange={handleChange}
                />
                {' '}Preferred Supplier
              </label>
              <label>
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                />
                {' '}Active
              </label>
            </div>
          </form>
        </div>

        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button 
            type="submit" 
            onClick={handleSubmit} 
            disabled={loading} 
            className="btn btn-primary"
          >
            {loading ? 'Saving...' : supplier ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SupplierForm;
