import React, { useState, useEffect } from 'react';
import { Plus, Pencil, Shield, Trash2 } from 'lucide-react';
import { rolesAPI, permissionsAPI } from '../../services/api';
import RoleForm from './RoleForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import {
  usersEnableRoleCreate,
  usersEnableRoleEdit,
  usersEnableRoleDelete,
  usersEnablePermissionCatalog,
} from '../../utils/userDisplay';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  SearchField,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ActiveStatusBadge,
} from '../page';

const Roles = () => {
  const { settings: userSettings } = useModuleSettings('users');
  const canCreateRole = usersEnableRoleCreate(userSettings);
  const canEditRole = usersEnableRoleEdit(userSettings);
  const canDeleteRole = usersEnableRoleDelete(userSettings);
  const showPermissionCatalog = usersEnablePermissionCatalog(userSettings);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [permissionCatalog, setPermissionCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [loadingRole, setLoadingRole] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    loadRoles();
    if (showPermissionCatalog) {
      loadPermissions();
    }
  }, [showPermissionCatalog]);

  const loadRoles = async () => {
    setLoading(true);
    try {
      const response = await rolesAPI.list();
      setRoles(response.data.results || response.data || []);
    } catch (error) {
      toast.error('Failed to load roles');
    } finally {
      setLoading(false);
    }
  };

  const loadPermissions = async () => {
    try {
      const domainRes = await permissionsAPI.byDomain();
      const catalog = domainRes.data?.catalog || [];
      if (catalog.length > 0) {
        setPermissionCatalog(catalog);
        const flat = [];
        catalog.forEach((domain) => {
          domain.modules.forEach((mod) => {
            mod.permissions.forEach((perm) => flat.push(perm));
          });
        });
        setPermissions(flat);
        return;
      }
    } catch (error) {
    }

    try {
      const response = await permissionsAPI.list({ page_size: 200 });
      const results = response.data.results || response.data || [];
      setPermissions(results);
      setPermissionCatalog([]);
    } catch (error) {
      toast.error('Failed to load permissions');
    }
  };

  const handleCreate = () => {
    setEditingRole(null);
    setShowForm(true);
  };

  const handleEdit = async (role) => {
    setLoadingRole(true);
    try {
      const response = await rolesAPI.get(role.id);
      setEditingRole(response.data);
      setShowForm(true);
    } catch (error) {
      toast.error('Failed to load role details');
    } finally {
      setLoadingRole(false);
    }
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
      toast.success('Role deleted');
      loadRoles();
    } catch (error) {
      toast.error('Failed to delete role');
    } finally {
      setConfirmDelete(null);
    }
  };

  const filteredRoles = roles.filter(
    (role) =>
      !searchQuery ||
      role.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      role.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <PageLoading rows={6} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Roles"
          description="Group permissions for managers, sales staff, and custom jobs."
        >
          {canCreateRole ? (
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4" />
            Add role
          </Button>
          ) : null}
        </PageHeader>

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search roles…"
            className="max-w-md"
          />
        </FilterBar>

        {filteredRoles.length === 0 ? (
          <EmptyState
            icon={Shield}
            title="No roles"
            description="Create a role to bundle permissions for your team."
            actionLabel={canCreateRole ? 'Add role' : undefined}
            onAction={canCreateRole ? handleCreate : undefined}
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Name</DataTableHead>
              <DataTableHead>Description</DataTableHead>
              <DataTableHead align="right">Permissions</DataTableHead>
              <DataTableHead align="right">Users</DataTableHead>
              <DataTableHead>Status</DataTableHead>
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {filteredRoles.map((role) => (
                <DataTableRow key={role.id}>
                  <DataTableCell className="font-medium">
                    {role.name}
                    {role.is_system_role && (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        System
                      </Badge>
                    )}
                  </DataTableCell>
                  <DataTableCell className="max-w-xs truncate text-muted-foreground">
                    {role.description || '—'}
                  </DataTableCell>
                  <DataTableCell align="right">{role.permissions_count || 0}</DataTableCell>
                  <DataTableCell align="right">{role.users_count || 0}</DataTableCell>
                  <DataTableCell>
                    <ActiveStatusBadge active={role.is_active} />
                  </DataTableCell>
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      {canEditRole ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={loadingRole}
                        onClick={() => handleEdit(role)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      ) : null}
                      {canDeleteRole ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        disabled={role.is_system_role}
                        onClick={() => handleDelete(role)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                      ) : null}
                    </div>
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        )}

        {showForm && (
          <RoleForm
            role={editingRole}
            permissions={permissions}
            permissionCatalog={permissionCatalog}
            showPermissionCatalog={showPermissionCatalog}
            onClose={() => {
              setShowForm(false);
              setEditingRole(null);
              loadRoles();
            }}
          />
        )}

        <ConfirmDialog
          isOpen={!!confirmDelete}
          title="Delete role"
          message={`Delete "${confirmDelete?.name}"? Users must be reassigned first.`}
          onConfirm={confirmDeleteAction}
          onCancel={() => setConfirmDelete(null)}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </PageShell>
  );
};

export default Roles;
