import React, { useState, useEffect } from 'react';
import { usersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';
import '../../styles/slide-in-panel.css';

const UserForm = ({ user, roles, onClose }) => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_staff: false,
    is_active: true,
    role: 'cashier',
    custom_role_id: null,
    phone_number: '',
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username || '',
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        password: '',
        is_staff: user.is_staff || false,
        is_active: user.is_active !== undefined ? user.is_active : true,
        role: user.profile?.role || 'cashier',
        custom_role_id: user.profile?.custom_role?.id || null,
        phone_number: user.profile?.phone_number || '',
      });
    }
  }, [user]);

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrors({});

    try {
      if (user) {
        // Update existing user
        const response = await usersAPI.update(user.id, formData);
        console.log('User updated:', response.data);
        toast.success('User updated successfully');
        // Wait a bit for backend to process, then close and refresh
        setTimeout(() => {
          onClose();
        }, 300);
      } else {
        // Create new user
        const response = await usersAPI.create(formData);
        console.log('User created:', response.data);
        toast.success('User created successfully');
        // Wait a bit for backend to process, then close and refresh
        setTimeout(() => {
          onClose();
        }, 300);
      }
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage = error.response.data.error || 
          Object.values(error.response.data).flat().join(', ') || 
          'Failed to save user';
        toast.error(errorMessage);
      } else {
        toast.error('Failed to save user: ' + (error.response?.data?.error || error.message));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{user ? 'Edit User' : 'Create New User'}</h2>
          <button className="slide-in-panel-close" onClick={onClose}>×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="user-form">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="username">Username *</label>
              <input
                type="text"
                id="username"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                disabled={!!user}
              />
              {errors.username && <span className="error">{errors.username}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
              />
              {errors.email && <span className="error">{errors.email}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">First Name</label>
              <input
                type="text"
                id="first_name"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="last_name">Last Name</label>
              <input
                type="text"
                id="last_name"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
              />
            </div>
          </div>

          {!user && (
            <div className="form-group">
              <label htmlFor="password">Password *</label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required={!user}
                minLength={6}
              />
              {errors.password && <span className="error">{errors.password}</span>}
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="role">Default Role</label>
              <SearchableSelect
                name="role"
                value={formData.role}
                onChange={handleChange}
                options={[
                  { id: 'cashier', name: 'Cashier' },
                  { id: 'manager', name: 'Manager' },
                  { id: 'admin', name: 'Admin' },
                  { id: 'super_admin', name: 'Super Admin' }
                ]}
                placeholder="Select Default Role"
              />
            </div>

            <div className="form-group">
              <label htmlFor="custom_role_id">Custom Role</label>
              <SearchableSelect
                name="custom_role_id"
                value={formData.custom_role_id || ''}
                onChange={handleChange}
                options={[
                  { id: '', name: 'None' },
                  ...roles.map(role => ({ id: role.id, name: role.name }))
                ]}
                placeholder="None"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="phone_number">Phone Number</label>
            <input
              type="text"
              id="phone_number"
              name="phone_number"
              value={formData.phone_number}
              onChange={handleChange}
            />
          </div>

          <div className="form-row">
            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="is_staff"
                  checked={formData.is_staff}
                  onChange={handleChange}
                />
                Staff Member
              </label>
            </div>

            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                />
                Active
              </label>
            </div>
          </div>

          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" onClick={handleSubmit} className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : (user ? 'Update' : 'Create')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserForm;

