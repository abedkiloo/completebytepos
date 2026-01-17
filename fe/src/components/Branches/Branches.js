import React, { useState, useEffect } from 'react';
import { branchesAPI, usersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import Layout from '../Layout/Layout';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import '../../styles/slide-in-panel.css';
import './Branches.css';

const Branches = () => {
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [users, setUsers] = useState([]);
  const [formData, setFormData] = useState({
    branch_code: '',
    name: '',
    address: '',
    city: '',
    country: 'Kenya',
    phone: '',
    email: '',
    is_active: true,
    is_headquarters: false,
    manager: '',
    tenant_id: '',  // Will be set automatically from current tenant
  });
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadBranches();
    loadUsers();
  }, []);

  const loadBranches = async () => {
    setLoading(true);
    try {
      const response = await branchesAPI.list({ is_active: 'true' });
      const branchesData = response.data.results || response.data || [];
      setBranches(Array.isArray(branchesData) ? branchesData : []);
    } catch (error) {
      console.error('Error loading branches:', error);
      toast.error('Failed to load branches');
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const response = await usersAPI.list({ is_active: 'true' });
      const usersData = response.data.results || response.data || [];
      setUsers(Array.isArray(usersData) ? usersData : []);
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const handleCreate = () => {
    setSelectedBranch(null);
    setFormData({
      branch_code: '',
      name: '',
      address: '',
      city: '',
      country: 'Kenya',
      phone: '',
      email: '',
      is_active: true,
      is_headquarters: false,
      manager: '',
    });
    setShowModal(true);
  };

  const handleEdit = (branch) => {
    setSelectedBranch(branch);
    setFormData({
      branch_code: branch.branch_code || '',
      name: branch.name || '',
      address: branch.address || '',
      city: branch.city || '',
      country: branch.country || 'Kenya',
      phone: branch.phone || '',
      email: branch.email || '',
      is_active: branch.is_active !== undefined ? branch.is_active : true,
      is_headquarters: branch.is_headquarters || false,
      manager: branch.manager || '',
    });
    setShowModal(true);
  };

  const handleDelete = (branch) => {
    setSelectedBranch(branch);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedBranch) return;
    
    try {
      await branchesAPI.delete(selectedBranch.id);
      toast.success('Branch deleted successfully');
      loadBranches();
      setShowDeleteConfirm(false);
      setSelectedBranch(null);
    } catch (error) {
      toast.error('Failed to delete branch: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const branchData = {
        ...formData,
        manager: formData.manager || null,
      };
      
      if (selectedBranch) {
        await branchesAPI.update(selectedBranch.id, branchData);
        toast.success('Branch updated successfully');
      } else {
        await branchesAPI.create(branchData);
        toast.success('Branch created successfully');
      }
      setShowModal(false);
      loadBranches();
      setSelectedBranch(null);
    } catch (error) {
      toast.error('Failed to save branch: ' + (error.response?.data?.error || error.message));
    }
  };

  const filteredBranches = branches.filter(branch => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      branch.name.toLowerCase().includes(query) ||
      branch.branch_code.toLowerCase().includes(query) ||
      (branch.city && branch.city.toLowerCase().includes(query))
    );
  });

  return (
    <Layout>
      <div className="branches-container">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Branch Management</h1>
            <p>Manage branches and locations</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={handleCreate}>
              <span>+</span>
              <span>Create Branch</span>
            </button>
          </div>
        </div>

        <div className="branches-toolbar">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search branches..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <span className="search-icon">🔍</span>
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading branches...</div>
        ) : (
          <div className="branches-table-container">
            <table className="branches-table">
              <thead>
                <tr>
                  <th>Branch Code</th>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Manager</th>
                  <th>Status</th>
                  <th>Type</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredBranches.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty-state">
                      No branches found
                    </td>
                  </tr>
                ) : (
                  filteredBranches.map(branch => (
                    <tr key={branch.id}>
                      <td>
                        <strong>{branch.branch_code}</strong>
                      </td>
                      <td>{branch.name}</td>
                      <td>
                        {branch.city && <span>{branch.city}</span>}
                        {branch.city && branch.country && <span>, </span>}
                        {branch.country && <span>{branch.country}</span>}
                      </td>
                      <td>
                        {branch.manager_name || 'N/A'}
                      </td>
                      <td>
                        <span className={`status-badge ${branch.is_active ? 'active' : 'inactive'}`}>
                          {branch.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        {branch.is_headquarters && (
                          <span className="badge badge-hq">Headquarters</span>
                        )}
                      </td>
                      <td>
                        <div className="action-buttons">
                          <button onClick={() => handleEdit(branch)} className="btn-edit">Edit</button>
                          <button onClick={() => handleDelete(branch)} className="btn-delete">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Branch Modal */}
        {showModal && (
          <div className="slide-in-overlay" onClick={() => setShowModal(false)}>
            <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
              <div className="slide-in-panel-header">
                <h2>{selectedBranch ? 'Edit Branch' : 'Create Branch'}</h2>
                <button onClick={() => setShowModal(false)} className="slide-in-panel-close">×</button>
              </div>
              <div className="slide-in-panel-body">
                <form onSubmit={handleSubmit}>
                <div className="form-row">
                  <div className="form-group">
                    <label>Branch Code *</label>
                    <input
                      type="text"
                      value={formData.branch_code}
                      onChange={(e) => setFormData({ ...formData, branch_code: e.target.value })}
                      required
                      placeholder="e.g., BR001"
                    />
                  </div>
                  <div className="form-group">
                    <label>Branch Name *</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      placeholder="e.g., Nairobi Main Branch"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Address</label>
                  <textarea
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    rows="2"
                    placeholder="Street address"
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>City</label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      placeholder="City"
                    />
                  </div>
                  <div className="form-group">
                    <label>Country</label>
                    <input
                      type="text"
                      value={formData.country}
                      onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                      placeholder="Country"
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Phone</label>
                    <input
                      type="text"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="Phone number"
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="Email address"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Manager</label>
                  <select
                    value={formData.manager}
                    onChange={(e) => setFormData({ ...formData, manager: e.target.value })}
                  >
                    <option value="">Select Manager</option>
                    {users.map(user => (
                      <option key={user.id} value={user.id}>
                        {user.username} {user.first_name && `(${user.first_name} ${user.last_name || ''})`}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      />
                      <span>Active</span>
                    </label>
                  </div>
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_headquarters}
                        onChange={(e) => setFormData({ ...formData, is_headquarters: e.target.checked })}
                      />
                      <span>Headquarters</span>
                    </label>
                  </div>
                </div>
                </form>
              </div>
              <div className="slide-in-panel-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" onClick={handleSubmit} className="btn btn-primary">
                  {selectedBranch ? 'Update' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Branch"
          message={`Are you sure you want to delete branch ${selectedBranch?.name}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedBranch(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </div>
    </Layout>
  );
};

export default Branches;
