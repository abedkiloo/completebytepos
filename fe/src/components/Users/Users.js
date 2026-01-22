import React, { useState, useEffect } from 'react';
import { usersAPI, rolesAPI } from '../../services/api';
import Layout from '../Layout/Layout';
import UserForm from './UserForm';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import './Users.css';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  useEffect(() => {
    loadUsers();
    loadRoles();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      // Request all users (no pagination limit for now)
      const response = await usersAPI.list({ page_size: 1000 });
      const usersData = response.data.results || response.data || [];
      const usersArray = Array.isArray(usersData) ? usersData : [];
      console.log(`Loaded ${usersArray.length} users`);
      setUsers(usersArray);
    } catch (error) {
      console.error('Error loading users:', error);
      toast.error('Failed to load users: ' + (error.response?.data?.error || error.message));
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const loadRoles = async () => {
    try {
      const response = await rolesAPI.list();
      setRoles(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading roles:', error);
    }
  };

  const handleCreate = () => {
    setEditingUser(null);
    setShowForm(true);
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setShowForm(true);
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Are you sure you want to delete user "${user.username}"?`)) {
      return;
    }

    try {
      await usersAPI.delete(user.id);
      toast.success('User deleted successfully');
      loadUsers();
    } catch (error) {
      toast.error('Failed to delete user: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleAssignRole = async (user, roleId) => {
    try {
      await usersAPI.assignRole(user.id, roleId);
      toast.success('Role assigned successfully');
      loadUsers();
    } catch (error) {
      toast.error('Failed to assign role: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingUser(null);
    // Clear filters to ensure new user is visible
    setSearchQuery('');
    setFilterRole('all');
    setFilterStatus('all');
    // Reload users after a short delay to ensure backend has processed
    setTimeout(() => {
      loadUsers();
    }, 200);
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = !searchQuery || 
      user.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.first_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.last_name?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesRole = filterRole === 'all' || 
      user.profile?.role === filterRole ||
      user.profile?.custom_role?.id === parseInt(filterRole);
    
    const matchesStatus = filterStatus === 'all' ||
      (filterStatus === 'active' && user.is_active && user.profile?.is_active) ||
      (filterStatus === 'inactive' && (!user.is_active || !user.profile?.is_active));
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  const getRoleName = (user) => {
    if (user.profile?.custom_role) {
      return user.profile.custom_role.name;
    }
    if (user.profile?.role) {
      const roleMap = {
        'super_admin': 'Super Admin',
        'admin': 'Admin',
        'manager': 'Manager',
        'cashier': 'Cashier'
      };
      return roleMap[user.profile.role] || user.profile.role;
    }
    return 'No Role';
  };

  return (
    <Layout>
      <div className="users-page">
        <div className="page-header">
          <h2>User Management</h2>
          <button className="btn btn-primary" onClick={handleCreate}>
            <i className="fas fa-plus"></i> Add New User
          </button>
        </div>

        {/* Filters */}
        <div className="filters-card">
          <div className="filter-group">
            <label htmlFor="search">Search</label>
            <input
              type="text"
              id="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by username, email, name..."
            />
          </div>
          <div className="filter-group">
            <label htmlFor="filterRole">Role</label>
            <SearchableSelect
              value={filterRole}
              onChange={(e) => setFilterRole(e.target.value)}
              options={[
                { id: 'all', name: 'All Roles' },
                { id: 'super_admin', name: 'Super Admin' },
                { id: 'admin', name: 'Admin' },
                { id: 'manager', name: 'Manager' },
                { id: 'cashier', name: 'Cashier' },
                ...roles.map(role => ({ id: role.id, name: role.name }))
              ]}
              placeholder="All Roles"
            />
          </div>
          <div className="filter-group">
            <label htmlFor="filterStatus">Status</label>
            <SearchableSelect
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              options={[
                { id: 'all', name: 'All Status' },
                { id: 'active', name: 'Active' },
                { id: 'inactive', name: 'Inactive' }
              ]}
              placeholder="All Status"
            />
          </div>
        </div>

        {/* Users Table */}
        <div className="table-container">
          {loading ? (
            <div className="loading-state">Loading users...</div>
          ) : filteredUsers.length === 0 ? (
            <div className="empty-state">No users found.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map(user => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>{user.first_name} {user.last_name}</td>
                    <td>{user.email || 'N/A'}</td>
                    <td>
                      <SearchableSelect
                        value={user.profile?.custom_role?.id || user.profile?.role || ''}
                        onChange={(e) => {
                          const roleId = e.target.value;
                          if (roleId && roleId !== user.profile?.role) {
                            handleAssignRole(user, roleId);
                          }
                        }}
                        className="role-select"
                        options={[
                          { id: 'super_admin', name: 'Super Admin' },
                          { id: 'admin', name: 'Admin' },
                          { id: 'manager', name: 'Manager' },
                          { id: 'cashier', name: 'Cashier' },
                          ...roles.map(role => ({ id: role.id, name: role.name }))
                        ]}
                        placeholder="Select Role"
                      />
                    </td>
                    <td>
                      <span className={`status-badge ${user.is_active && user.profile?.is_active ? 'active' : 'inactive'}`}>
                        {user.is_active && user.profile?.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>{new Date(user.date_joined).toLocaleDateString()}</td>
                    <td className="action-buttons">
                      <button
                        className="btn btn-sm btn-info"
                        onClick={() => handleEdit(user)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(user)}
                        disabled={user.is_superuser}
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

        {/* User Form Modal */}
        {showForm && (
          <UserForm
            user={editingUser}
            roles={roles}
            onClose={handleFormClose}
          />
        )}
      </div>
    </Layout>
  );
};

export default Users;

