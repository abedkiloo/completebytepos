import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { rolesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { cn } from '../../lib/cn';
import { DOMAIN_ORDER, DOMAIN_LABELS } from '../../utils/moduleDomains';
import { Button } from '../ui/button';

function normalizeDomainCatalog(catalog) {
  if (!Array.isArray(catalog)) return [];
  return catalog.map((domain) => ({
    ...domain,
    modules: (domain.modules || []).map((mod) => ({
      ...mod,
      permissions: [...(mod.permissions || [])].sort((a, b) =>
        (a.action_display || a.action).localeCompare(b.action_display || b.action)
      ),
    })),
  }));
}

function buildDomainCatalogFromFlat(permissions) {
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

  const toDomainEntry = (domainId) => {
    const domain = byDomain[domainId];
    const modules = Object.values(domain.modules).sort((a, b) =>
      a.label.localeCompare(b.label)
    );
    return { ...domain, modules };
  };

  const ordered = DOMAIN_ORDER.filter((id) => byDomain[id]).map(toDomainEntry);
  const extra = Object.keys(byDomain)
    .filter((id) => !DOMAIN_ORDER.includes(id))
    .sort()
    .map(toDomainEntry);

  return [...ordered, ...extra];
}

function flattenCatalog(catalog) {
  const ids = [];
  catalog.forEach((domain) => {
    domain.modules.forEach((mod) => {
      mod.permissions.forEach((perm) => ids.push(perm.id));
    });
  });
  return ids;
}

const RoleForm = ({ role, permissions, permissionCatalog, showPermissionCatalog = true, onClose }) => {
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
    const catalog = permissionCatalog?.length
      ? normalizeDomainCatalog(permissionCatalog)
      : buildDomainCatalogFromFlat(permissions);
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
    } else {
      setFormData({
        name: '',
        description: '',
        is_active: true,
        permission_ids: [],
      });
    }
  }, [role, permissions, permissionCatalog]);

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

  const setPermissionIds = (updater) => {
    setFormData((prev) => ({
      ...prev,
      permission_ids: typeof updater === 'function' ? updater(prev.permission_ids) : updater,
    }));
  };

  const handlePermissionToggle = (permissionId) => {
    setPermissionIds((ids) =>
      ids.includes(permissionId)
        ? ids.filter((id) => id !== permissionId)
        : [...ids, permissionId]
    );
  };

  const handleModuleToggle = (modulePermissions) => {
    const ids = modulePermissions.map((p) => p.id);
    setPermissionIds((current) => {
      const allSelected = ids.every((id) => current.includes(id));
      return allSelected
        ? current.filter((id) => !ids.includes(id))
        : [...new Set([...current, ...ids])];
    });
  };

  const handleDomainToggle = (domain) => {
    const ids = flattenCatalog([domain]);
    setPermissionIds((current) => {
      const allSelected = ids.every((id) => current.includes(id));
      return allSelected
        ? current.filter((id) => !ids.includes(id))
        : [...new Set([...current, ...ids])];
    });
  };

  const handleSelectAll = () => {
    setPermissionIds(flattenCatalog(domainCatalog));
  };

  const handleClearAll = () => {
    setPermissionIds([]);
  };

  const toggleDomain = (domainId) => {
    setExpandedDomains((prev) => ({ ...prev, [domainId]: !prev[domainId] }));
  };

  const totalPermissions = flattenCatalog(domainCatalog).length;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrors({});

    const payload = {
      name: formData.name,
      description: formData.description,
      is_active: formData.is_active,
      permission_ids: formData.permission_ids,
    };

    try {
      if (role) {
        await rolesAPI.update(role.id, payload);
        toast.success('Role updated successfully');
      } else {
        await rolesAPI.create(payload);
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

            {showPermissionCatalog ? (
            <div className="permissions-section">
              <div className="permissions-header flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3>Permissions</h3>
                  <span className="selected-count">
                    {formData.permission_ids.length} of {totalPermissions} selected
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={handleSelectAll}>
                    Select all
                  </Button>
                  <Button type="button" variant="outline" size="sm" onClick={handleClearAll}>
                    Clear all
                  </Button>
                </div>
              </div>
              <p className="mb-3 text-xs text-muted-foreground">
                Select any combination of modules and actions for this role.
              </p>

              <div className="space-y-3">
                {domainCatalog.map((domain) => {
                  const domainIds = flattenCatalog([domain]);
                  const domainAllSelected = domainIds.every((id) =>
                    formData.permission_ids.includes(id)
                  );
                  const domainSomeSelected = domainIds.some((id) =>
                    formData.permission_ids.includes(id)
                  );

                  return (
                    <div
                      key={domain.id}
                      className="rounded-lg border border-border bg-card"
                    >
                      <div className="flex items-center gap-2 px-3 py-2">
                        <button
                          type="button"
                          className="flex flex-1 items-center gap-2 text-left text-sm font-semibold"
                          onClick={() => toggleDomain(domain.id)}
                        >
                          {expandedDomains[domain.id] ? (
                            <ChevronDown className="h-4 w-4 shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 shrink-0" />
                          )}
                          {domain.label}
                        </button>
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <input
                            type="checkbox"
                            checked={domainAllSelected}
                            ref={(input) => {
                              if (input) {
                                input.indeterminate =
                                  domainSomeSelected && !domainAllSelected;
                              }
                            }}
                            onChange={() => handleDomainToggle(domain)}
                          />
                          All
                        </label>
                      </div>

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
                  );
                })}
              </div>
            </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Permission catalog is hidden in store settings. Existing permissions on this role are preserved.
              </p>
            )}
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
