import React, { useState, useEffect } from 'react';
import { rolesAPI, permissionsAPI } from '../../services/api';
import Layout from '../Layout/Layout';
import RoleForm from './RoleForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import './Roles.css';

const Roles = () => {
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    loadRoles();
    loadPermissions();
  }, []);

  const loadRoles = async () => {
    setLoading(true);
    try {
      const response = await rolesAPI.list();
      setRoles(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading roles:', error);
      toast.error('Failed to load roles: ' + (error.response?.data?.error || error.message));
    } finally {
      setLoading(false);
    }
  };

  const loadPermissions = async () => {
    try {
      const response = await permissionsAPI.list();
      setPermissions(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading permissions:', error);
    }
  };

  const handleCreate = () => {
    setEditingRole(null);
    setShowForm(true);
  };

  const handleEdit = (role) => {
    setEditingRole(role);
    setShowForm(true);
  };

  const handleDelete = (role) => {
    if (role.is_system_role) {
      toast.warning('System roles cannot be deleted');
      return;
    }
    setConfirmDelete(role);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    
    try {
      await rolesAPI.delete(confirmDelete.id);
      toast.success('Role deleted successfully');
      loadRoles();
    } catch (error) {
      toast.error('Failed to delete role: ' + (error.response?.data?.error || error.message));
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingRole(null);
    loadRoles();
  };

  const filteredRoles = roles.filter(role =>
    !searchQuery ||
    role.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Layout>
      <div className="roles-page">
        <div className="page-header">
          <h2>Role Management</h2>
          <button className="btn btn-primary" onClick={handleCreate}>
            <i className="fas fa-plus"></i> Add New Role
          </button>
        </div>

        {/* Search */}
        <div className="filters-card">
          <div className="filter-group">
            <label htmlFor="search">Search</label>
            <input
              type="text"
              id="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search roles..."
            />
          </div>
        </div>

        {/* Roles Table */}
        <div className="table-container">
          {loading ? (
            <div className="loading-state">Loading roles...</div>
          ) : filteredRoles.length === 0 ? (
            <div className="empty-state">No roles found.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Permissions</th>
                  <th>Users</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRoles.map(role => (
                  <tr key={role.id}>
                    <td>
                      <strong>{role.name}</strong>
                      {role.is_system_role && (
                        <span className="system-badge">System</span>
                      )}
                    </td>
                    <td>{role.description || 'N/A'}</td>
                    <td>{role.permissions_count || 0}</td>
                    <td>{role.users_count || 0}</td>
                    <td>
                      {role.is_system_role ? (
                        <span className="type-badge system">System Role</span>
                      ) : (
                        <span className="type-badge custom">Custom Role</span>
                      )}
                    </td>
                    <td>
                      <span className={`status-badge ${role.is_active ? 'active' : 'inactive'}`}>
                        {role.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="action-buttons">
                      <button
                        className="btn btn-sm btn-info"
                        onClick={() => handleEdit(role)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(role)}
                        disabled={role.is_system_role}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Role Form Modal */}
        {showForm && (
          <RoleForm
            role={editingRole}
            permissions={permissions}
            onClose={handleFormClose}
          />
        )}

        {/* Confirm Delete Dialog */}
        <ConfirmDialog
          isOpen={!!confirmDelete}
          title="Delete Role"
          message={`Are you sure you want to delete role "${confirmDelete?.name}"?`}
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

export default Roles;

