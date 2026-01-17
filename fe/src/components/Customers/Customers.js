import React, { useState, useEffect } from 'react';
import { customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import '../../styles/shared.css';
import '../../styles/slide-in-panel.css';
import './Customers.css';

const Customers = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
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

  useEffect(() => {
    loadCustomers();
  }, [searchQuery]);

  const loadCustomers = async () => {
    setLoading(true);
    try {
      const params = { is_active: 'true' };
      if (searchQuery) {
        params.search = searchQuery;
      }
      const response = await customersAPI.list(params);
      const customersData = response.data.results || response.data || [];
      setCustomers(Array.isArray(customersData) ? customersData : []);
    } catch (error) {
      console.error('Error loading customers:', error);
      toast.error('Failed to load customers');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setSelectedCustomer(null);
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
    setShowModal(true);
  };

  const handleEdit = (customer) => {
    setSelectedCustomer(customer);
    setFormData({
      name: customer.name || '',
      customer_type: customer.customer_type || 'individual',
      email: customer.email || '',
      phone: customer.phone || '',
      address: customer.address || '',
      city: customer.city || '',
      country: customer.country || 'Kenya',
      tax_id: customer.tax_id || '',
      notes: customer.notes || '',
      is_active: customer.is_active !== undefined ? customer.is_active : true,
    });
    setShowModal(true);
  };

  const handleDelete = (customer) => {
    setSelectedCustomer(customer);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedCustomer) return;
    
    try {
      await customersAPI.delete(selectedCustomer.id);
      toast.success('Customer deleted successfully');
      loadCustomers();
      setShowDeleteConfirm(false);
      setSelectedCustomer(null);
    } catch (error) {
      toast.error('Failed to delete customer: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      if (selectedCustomer) {
        await customersAPI.update(selectedCustomer.id, formData);
        toast.success('Customer updated successfully');
      } else {
        await customersAPI.create(formData);
        toast.success('Customer created successfully');
      }
      setShowModal(false);
      loadCustomers();
      setSelectedCustomer(null);
    } catch (error) {
      toast.error('Failed to save customer: ' + (error.response?.data?.error || error.message));
    }
  };

  return (
    <Layout>
      <div className="customers-container">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Customers</h1>
            <p>Manage your customer database</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={handleCreate}>
              <span>+</span>
              <span>Add Customer</span>
            </button>
          </div>
        </div>

        <div className="customers-toolbar">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <span className="search-icon">🔍</span>
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading customers...</div>
        ) : (
          <div className="customers-table-container">
            <table className="customers-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>City</th>
                  <th>Outstanding</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {customers.length === 0 ? (
                  <tr>
                    <td colSpan="9" className="empty-state">
                      No customers found
                    </td>
                  </tr>
                ) : (
                  customers.map(customer => (
                    <tr key={customer.id} className={!customer.is_active ? 'inactive' : ''}>
                      <td>{customer.customer_code}</td>
                      <td>
                        <div className="customer-name">{customer.name}</div>
                      </td>
                      <td>
                        <span className={`type-badge ${customer.customer_type}`}>
                          {customer.customer_type === 'business' ? 'Business' : 'Individual'}
                        </span>
                      </td>
                      <td>{customer.email || '-'}</td>
                      <td>{customer.phone || '-'}</td>
                      <td>{customer.city || '-'}</td>
                      <td>
                        <span className={customer.total_outstanding > 0 ? 'outstanding' : 'paid'}>
                          {formatCurrency(customer.total_outstanding || 0)}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${customer.is_active ? 'active' : 'inactive'}`}>
                          {customer.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        <div className="action-buttons">
                          <button onClick={() => handleEdit(customer)} className="btn-edit">Edit</button>
                          <button onClick={() => handleDelete(customer)} className="btn-delete">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Customer Modal */}
        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal-content customer-modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>{selectedCustomer ? 'Edit Customer' : 'Add Customer'}</h2>
                <button onClick={() => setShowModal(false)} className="close-btn">×</button>
              </div>
              <form onSubmit={handleSubmit}>
                <div className="form-row">
                  <div className="form-group">
                    <label>Name *</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label>Type *</label>
                    <select
                      value={formData.customer_type}
                      onChange={(e) => setFormData({ ...formData, customer_type: e.target.value })}
                      required
                    >
                      <option value="individual">Individual</option>
                      <option value="business">Business</option>
                    </select>
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
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
                  <textarea
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    rows="2"
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
                  <label>Tax ID / VAT Number</label>
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
                <div className="form-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    />
                    Active
                  </label>
                </div>
                </form>
              </div>
              <div className="slide-in-panel-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" onClick={handleSubmit} className="btn btn-primary">
                  {selectedCustomer ? 'Update' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Customer"
          message={`Are you sure you want to delete ${selectedCustomer?.name}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedCustomer(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </div>
    </Layout>
  );
};

export default Customers;

