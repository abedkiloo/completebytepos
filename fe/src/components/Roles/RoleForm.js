import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { rolesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { cn } from '../../lib/cn';
import { DOMAIN_ORDER, DOMAIN_LABELS } from '../../utils/moduleDomains';

function buildDomainCatalog(permissions) {
  const byDomain = {};

  permissions.forEach((perm) => {
    const domainId = perm.domain || 'platform';
    const domainLabel = perm.domain_label || DOMAIN_LABELS[domainId] || domainId;
    const modKey = perm.catalog_module || perm.module;
    const modLabel =
      perm.catalog_module_label || perm.module_display || perm.module;

    if (!byDomain[domainId]) {
      byDomain[domainId] = { id: domainId, label: domainLabel, modules: {} };
    }
    if (!byDomain[domainId].modules[modKey]) {
      byDomain[domainId].modules[modKey] = { id: modKey, label: modLabel, permissions: [] };
    }
    byDomain[domainId].modules[modKey].permissions.push(perm);
  });

  return DOMAIN_ORDER.filter((id) => byDomain[id]).map((domainId) => {
    const domain = byDomain[domainId];
    const modules = Object.values(domain.modules).sort((a, b) =>
      a.label.localeCompare(b.label)
    );
    modules.forEach((m) => {
      m.permissions.sort((a, b) =>
        (a.action_display || a.action).localeCompare(b.action_display || b.action)
      );
    });
    return { ...domain, modules };
  });
}

const RoleForm = ({ role, permissions, onClose }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    is_active: true,
    permission_ids: [],
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [domainCatalog, setDomainCatalog] = useState([]);
  const [expandedDomains, setExpandedDomains] = useState({});

  useEffect(() => {
    const catalog = buildDomainCatalog(permissions);
    setDomainCatalog(catalog);
    const expanded = {};
    catalog.forEach((d) => {
      expanded[d.id] = true;
    });
    setExpandedDomains(expanded);

    if (role) {
      setFormData({
        name: role.name || '',
        description: role.description || '',
        is_active: role.is_active !== undefined ? role.is_active : true,
        permission_ids: role.permissions?.map((p) => p.id) || [],
      });
    }
  }, [role, permissions]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handlePermissionToggle = (permissionId) => {
    setFormData((prev) => ({
      ...prev,
      permission_ids: prev.permission_ids.includes(permissionId)
        ? prev.permission_ids.filter((id) => id !== permissionId)
        : [...prev.permission_ids, permissionId],
    }));
  };

  const handleModuleToggle = (modulePermissions) => {
    const ids = modulePermissions.map((p) => p.id);
    const allSelected = ids.every((id) => formData.permission_ids.includes(id));
    setFormData((prev) => ({
      ...prev,
      permission_ids: allSelected
        ? prev.permission_ids.filter((id) => !ids.includes(id))
        : [...new Set([...prev.permission_ids, ...ids])],
    }));
  };

  const toggleDomain = (domainId) => {
    setExpandedDomains((prev) => ({ ...prev, [domainId]: !prev[domainId] }));
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
        const errorMessage =
          error.response.data.error ||
          Object.values(error.response.data).flat().join(', ') ||
          'Failed to save role';
        toast.error(errorMessage);
      } else {
        toast.error(
          'Failed to save role: ' + (error.response?.data?.error || error.message)
        );
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
          <button type="button" className="slide-in-panel-close" onClick={onClose}>
            ×
          </button>
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
                  {formData.permission_ids.length} selected
                </span>
              </div>
              <p className="mb-3 text-xs text-muted-foreground">
                Grouped by the same business areas as Module Settings.
              </p>

              <div className="space-y-3">
                {domainCatalog.map((domain) => (
                  <div
                    key={domain.id}
                    className="rounded-lg border border-border bg-card"
                  >
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold"
                      onClick={() => toggleDomain(domain.id)}
                    >
                      {expandedDomains[domain.id] ? (
                        <ChevronDown className="h-4 w-4 shrink-0" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0" />
                      )}
                      {domain.label}
                    </button>

                    {expandedDomains[domain.id] && (
                      <div className="space-y-2 border-t border-border px-3 pb-3 pt-2">
                        {domain.modules.map((mod) => {
                          const allSelected = mod.permissions.every((p) =>
                            formData.permission_ids.includes(p.id)
                          );
                          const someSelected = mod.permissions.some((p) =>
                            formData.permission_ids.includes(p.id)
                          );

                          return (
                            <div key={mod.id} className="permission-module">
                              <div className="module-header">
                                <label className="module-checkbox flex items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={allSelected}
                                    ref={(input) => {
                                      if (input) {
                                        input.indeterminate =
                                          someSelected && !allSelected;
                                      }
                                    }}
                                    onChange={() =>
                                      handleModuleToggle(mod.permissions)
                                    }
                                  />
                                  <strong className="text-sm">{mod.label}</strong>
                                </label>
                              </div>
                              <div
                                className={cn(
                                  'permission-items ml-6 grid gap-1',
                                  'sm:grid-cols-2'
                                )}
                              >
                                {mod.permissions.map((perm) => (
                                  <label
                                    key={perm.id}
                                    className="permission-item flex items-center gap-2 text-sm"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={formData.permission_ids.includes(
                                        perm.id
                                      )}
                                      onChange={() =>
                                        handlePermissionToggle(perm.id)
                                      }
                                    />
                                    <span>
                                      {perm.action_display || perm.action}
                                    </span>
                                  </label>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Saving...' : role ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoleForm;
