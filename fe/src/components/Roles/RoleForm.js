import React, { useState, useEffect } from 'react';
import { rolesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

const RoleForm = ({ role, permissions, onClose }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true,
    permission_ids: [],
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [permissionsByModule, setPermissionsByModule] = useState({});

  useEffect(() => {
    // Group permissions by module
    const grouped = {};
    permissions.forEach(perm => {
      const module = perm.module_display || perm.module;
      if (!grouped[module]) {
        grouped[module] = [];
      }
      grouped[module].push(perm);
    });
    setPermissionsByModule(grouped);

    if (role) {
      setFormData({
        name: role.name || '',
        description: role.description || '',
        is_active: role.is_active !== undefined ? role.is_active : true,
        permission_ids: role.permissions?.map(p => p.id) || [],
      });
    }
  }, [role, permissions]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const handlePermissionToggle = (permissionId) => {
    setFormData(prev => ({
      ...prev,
      permission_ids: prev.permission_ids.includes(permissionId)
        ? prev.permission_ids.filter(id => id !== permissionId)
        : [...prev.permission_ids, permissionId]
    }));
  };

  const handleModuleToggle = (modulePermissions) => {
    const allSelected = modulePermissions.every(p => formData.permission_ids.includes(p.id));
    setFormData(prev => ({
      ...prev,
      permission_ids: allSelected
        ? prev.permission_ids.filter(id => !modulePermissions.some(p => p.id === id))
        : [...new Set([...prev.permission_ids, ...modulePermissions.map(p => p.id)])]
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrors({});

    try {
      if (role) {
        await rolesAPI.update(role.id, formData);
        toast.success('Role updated successfully');
      } else {
        await rolesAPI.create(formData);
        toast.success('Role created successfully');
      }
      setTimeout(() => {
        onClose();
      }, 500);
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage = error.response.data.error || 
          Object.values(error.response.data).flat().join(', ') || 
          'Failed to save role';
        toast.error(errorMessage);
      } else {
        toast.error('Failed to save role: ' + (error.response?.data?.error || error.message));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{role ? 'Edit Role' : 'Create New Role'}</h2>
          <button className="slide-in-panel-close" onClick={onClose}>×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="role-form">
          <div className="form-group">
            <label htmlFor="name">Role Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={role?.is_system_role}
            />
            {errors.name && <span className="error">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
            />
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

          <div className="permissions-section">
            <div className="permissions-header">
              <h3>Permissions</h3>
              <span className="selected-count">
                {formData.permission_ids.length} permission(s) selected
              </span>
            </div>

            <div className="permissions-list">
              {Object.entries(permissionsByModule).map(([module, modulePermissions]) => {
                const allSelected = modulePermissions.every(p => formData.permission_ids.includes(p.id));
                const someSelected = modulePermissions.some(p => formData.permission_ids.includes(p.id));

                return (
                  <div key={module} className="permission-module">
                    <div className="module-header">
                      <label className="module-checkbox">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          ref={input => {
                            if (input) input.indeterminate = someSelected && !allSelected;
                          }}
                          onChange={() => handleModuleToggle(modulePermissions)}
                        />
                        <strong>{module}</strong>
                      </label>
                    </div>
                    <div className="permission-items">
                      {modulePermissions.map(perm => (
                        <label key={perm.id} className="permission-item">
                          <input
                            type="checkbox"
                            checked={formData.permission_ids.includes(perm.id)}
                            onChange={() => handlePermissionToggle(perm.id)}
                          />
                          <span>{perm.action_display || perm.action}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" onClick={handleSubmit} className="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : (role ? 'Update' : 'Create')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoleForm;

