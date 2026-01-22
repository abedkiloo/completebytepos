import React, { useState } from 'react';
import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';
import '../../styles/slide-in-panel.css';
import './Customers.css';

const CustomerFormModal = ({ isOpen, onClose, onCustomerCreated }) => {
  const [formData, setFormData] = useState({
    name: '',
    customer_type: 'individual',
    email: '',
    phone: '',
    address: '',
    city: '',
    country: 'Kenya',
    tax_id: '',
    notes: '',
    is_active: true,
  });
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const handleClose = () => {
    // Reset form when closing
    setFormData({
      name: '',
      customer_type: 'individual',
      email: '',
      phone: '',
      address: '',
      city: '',
      country: 'Kenya',
      tax_id: '',
      notes: '',
      is_active: true,
    });
    setFormErrors({});
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Clear previous errors
    setFormErrors({});
    
    // Client-side validation
    const errors = {};
    
    if (!formData.name || !formData.name.trim()) {
      errors.name = 'Customer name is required';
    } else if (formData.name.trim().length < 2) {
      errors.name = 'Customer name must be at least 2 characters';
    }
    
    // Validate email format if provided
    if (formData.email && formData.email.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email.trim())) {
        errors.email = 'Please enter a valid email address';
      }
    }
    
    // If there are client-side errors, show them and return
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      toast.error(Object.values(errors)[0], 5000);
      return;
    }
    
    setLoading(true);
    
    // Prepare clean data
    const cleanData = {
      name: formData.name.trim(),
      customer_type: formData.customer_type,
      email: formData.email.trim() || '',
      phone: formData.phone.trim() || '',
      address: formData.address.trim() || '',
      city: formData.city.trim() || '',
      country: formData.country.trim() || 'Kenya',
      tax_id: formData.tax_id.trim() || '',
      notes: formData.notes.trim() || '',
      is_active: formData.is_active,
    };
    
    try {
      const response = await customersAPI.create(cleanData);
      const newCustomer = response.data;
      toast.success('Customer created successfully');
      handleClose();
      
      // Call callback with the new customer
      if (onCustomerCreated) {
        onCustomerCreated(newCustomer);
      }
    } catch (error) {
      // Handle validation errors from backend
      const backendErrors = {};
      let errorMessage = 'Failed to create customer';
      
      if (error.response?.data) {
        const errorData = error.response.data;
        
        // Handle field-level validation errors (DRF format)
        if (typeof errorData === 'object' && !errorData.error) {
          for (const [field, messages] of Object.entries(errorData)) {
            if (Array.isArray(messages)) {
              backendErrors[field] = messages.join(', ');
            } else if (typeof messages === 'string') {
              backendErrors[field] = messages;
            } else {
              backendErrors[field] = JSON.stringify(messages);
            }
          }
          if (Object.keys(backendErrors).length > 0) {
            setFormErrors(backendErrors);
            errorMessage = Object.values(backendErrors)[0];
            toast.error(errorMessage, 8000);
            setLoading(false);
            return; // Don't close modal on validation error
          }
        } else if (errorData.error) {
          errorMessage = errorData.error;
        } else if (typeof errorData === 'string') {
          errorMessage = errorData;
        } else if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage, 8000);
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="slide-in-overlay" onClick={handleClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Add New Customer</h2>
          <button onClick={handleClose} className="slide-in-panel-close">×</button>
        </div>
        
        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (formErrors.name) setFormErrors({ ...formErrors, name: '' });
                  }}
                  className={formErrors.name ? 'error' : ''}
                  required
                  autoFocus
                />
                {formErrors.name && <span className="error-text">{formErrors.name}</span>}
              </div>
              <div className="form-group">
                <label>Type *</label>
                <SearchableSelect
                  value={formData.customer_type}
                  onChange={(e) => setFormData({ ...formData, customer_type: e.target.value })}
                  options={[
                    { id: 'individual', name: 'Individual' },
                    { id: 'business', name: 'Business' }
                  ]}
                  placeholder="Select Type"
                />
              </div>
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => {
                    setFormData({ ...formData, email: e.target.value });
                    if (formErrors.email) setFormErrors({ ...formErrors, email: '' });
                  }}
                  className={formErrors.email ? 'error' : ''}
                />
                {formErrors.email && <span className="error-text">{formErrors.email}</span>}
              </div>
              <div className="form-group">
                <label>Phone</label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                />
              </div>
            </div>
            
            <div className="form-group">
              <label>Address</label>
              <input
                type="text"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              />
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label>City</label>
                <input
                  type="text"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Country</label>
                <input
                  type="text"
                  value={formData.country}
                  onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                />
              </div>
            </div>
            
            <div className="form-group">
              <label>Tax ID</label>
              <input
                type="text"
                value={formData.tax_id}
                onChange={(e) => setFormData({ ...formData, tax_id: e.target.value })}
              />
            </div>
            
            <div className="form-group">
              <label>Notes</label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows="3"
              />
            </div>
          </form>
        </div>
        
        <div className="slide-in-panel-footer">
          <button 
            type="button" 
            onClick={handleClose} 
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            type="button" 
            onClick={handleSubmit} 
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Creating...' : 'Create Customer'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CustomerFormModal;
