import React, { useState, useEffect } from 'react';
import { suppliersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import SupplierForm from './SupplierForm';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import '../../styles/shared.css';
import '../../styles/slide-in-panel.css';
import './Suppliers.css';

const Suppliers = () => {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [filters, setFilters] = useState({
    is_active: '',
    supplier_type: '',
    is_preferred: '',
  });
  const [statistics, setStatistics] = useState(null);

  useEffect(() => {
    loadSuppliers();
    loadStatistics();
  }, [searchQuery, filters]);

  const loadSuppliers = async () => {
    setLoading(true);
    try {
      const params = {};
      if (searchQuery) {
        params.search = searchQuery;
      }
      if (filters.is_active !== '') {
        params.is_active = filters.is_active;
      }
      if (filters.supplier_type) {
        params.supplier_type = filters.supplier_type;
      }
      if (filters.is_preferred !== '') {
        params.is_preferred = filters.is_preferred;
      }
      
      const response = await suppliersAPI.list(params);
      const suppliersData = response.data.results || response.data || [];
      setSuppliers(Array.isArray(suppliersData) ? suppliersData : []);
    } catch (error) {
      console.error('Error loading suppliers:', error);
      toast.error('Failed to load suppliers');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await suppliersAPI.statistics();
      setStatistics(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const handleCreate = () => {
    setSelectedSupplier(null);
    setShowForm(true);
  };

  const handleEdit = (supplier) => {
    setSelectedSupplier(supplier);
    setShowForm(true);
  };

  const handleDelete = (supplier) => {
    setSelectedSupplier(supplier);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedSupplier) return;
    
    try {
      await suppliersAPI.delete(selectedSupplier.id);
      toast.success('Supplier deleted successfully');
      loadSuppliers();
      loadStatistics();
      setShowDeleteConfirm(false);
      setSelectedSupplier(null);
    } catch (error) {
      toast.error('Failed to delete supplier: ' + (error.response?.data?.error || error.message));
      setShowDeleteConfirm(false);
    }
  };

  const handleSave = () => {
    loadSuppliers();
    loadStatistics();
    setShowForm(false);
    setSelectedSupplier(null);
  };

  const getSupplierTypeDisplay = (type) => {
    const types = {
      'individual': 'Individual',
      'business': 'Business',
      'manufacturer': 'Manufacturer',
      'distributor': 'Distributor',
      'wholesaler': 'Wholesaler',
    };
    return types[type] || type;
  };

  const getPaymentTermsDisplay = (terms) => {
    const termsMap = {
      'net_15': 'Net 15',
      'net_30': 'Net 30',
      'net_45': 'Net 45',
      'net_60': 'Net 60',
      'cod': 'Cash on Delivery',
      'prepaid': 'Prepaid',
      'custom': 'Custom Terms',
    };
    return termsMap[terms] || terms;
  };

  return (
    <Layout>
      <div className="suppliers-container">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Suppliers</h1>
            <p>Manage your supplier database</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={handleCreate}>
              + Add Supplier
            </button>
          </div>
        </div>

        {/* Statistics Cards */}
        {statistics && (
          <div className="statistics-grid">
            <div className="stat-card">
              <div className="stat-label">Total Suppliers</div>
              <div className="stat-value">{statistics.total_suppliers || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Active Suppliers</div>
              <div className="stat-value">{statistics.active_suppliers || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Preferred Suppliers</div>
              <div className="stat-value">{statistics.preferred_suppliers || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Account Balance</div>
              <div className="stat-value">{formatCurrency(statistics.total_account_balance || 0)}</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="filters-section">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search suppliers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="filter-controls">
            <select
              value={filters.is_active}
              onChange={(e) => setFilters({ ...filters, is_active: e.target.value })}
            >
              <option value="">All Status</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
            <select
              value={filters.supplier_type}
              onChange={(e) => setFilters({ ...filters, supplier_type: e.target.value })}
            >
              <option value="">All Types</option>
              <option value="individual">Individual</option>
              <option value="business">Business</option>
              <option value="manufacturer">Manufacturer</option>
              <option value="distributor">Distributor</option>
              <option value="wholesaler">Wholesaler</option>
            </select>
            <select
              value={filters.is_preferred}
              onChange={(e) => setFilters({ ...filters, is_preferred: e.target.value })}
            >
              <option value="">All Suppliers</option>
              <option value="true">Preferred Only</option>
            </select>
          </div>
        </div>

        {/* Suppliers Table */}
        {loading ? (
          <div className="loading">Loading suppliers...</div>
        ) : suppliers.length === 0 ? (
          <div className="empty-state">
            <p>No suppliers found</p>
            <button className="btn btn-primary" onClick={handleCreate}>
              Add First Supplier
            </button>
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Contact Person</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>City</th>
                  <th>Payment Terms</th>
                  <th>Credit Limit</th>
                  <th>Account Balance</th>
                  <th>Rating</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    <td>{supplier.supplier_code}</td>
                    <td>
                      <div className="supplier-name-cell">
                        <strong>{supplier.name}</strong>
                        {supplier.is_preferred && (
                          <span className="badge preferred">Preferred</span>
                        )}
                      </div>
                    </td>
                    <td>{getSupplierTypeDisplay(supplier.supplier_type)}</td>
                    <td>{supplier.contact_person || '-'}</td>
                    <td>{supplier.email || '-'}</td>
                    <td>{supplier.phone || '-'}</td>
                    <td>{supplier.city || '-'}</td>
                    <td>{getPaymentTermsDisplay(supplier.payment_terms)}</td>
                    <td>{formatCurrency(supplier.credit_limit || 0)}</td>
                    <td>
                      <span className={supplier.account_balance > 0 ? 'balance-owed' : ''}>
                        {formatCurrency(supplier.account_balance || 0)}
                      </span>
                    </td>
                    <td>
                      <div className="rating-stars">
                        {'★'.repeat(supplier.rating || 0)}
                        {'☆'.repeat(5 - (supplier.rating || 0))}
                      </div>
                    </td>
                    <td>
                      <span className={`status-badge ${supplier.is_active ? 'active' : 'inactive'}`}>
                        {supplier.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button onClick={() => handleEdit(supplier)} className="btn-edit">Edit</button>
                        <button onClick={() => handleDelete(supplier)} className="btn-delete">Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Supplier Form */}
        {showForm && (
          <SupplierForm
            supplier={selectedSupplier}
            onClose={() => {
              setShowForm(false);
              setSelectedSupplier(null);
            }}
            onSave={handleSave}
          />
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Supplier"
          message={`Are you sure you want to delete ${selectedSupplier?.name}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedSupplier(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </div>
    </Layout>
  );
};

export default Suppliers;
