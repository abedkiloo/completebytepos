import React, { useState, useEffect } from 'react';
import { Plus, Pencil, Shield, Trash2 } from 'lucide-react';
import { rolesAPI, permissionsAPI } from '../../services/api';
import Layout from '../Layout/Layout';
import RoleForm from './RoleForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
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
      toast.error('Failed to load roles');
    } finally {
      setLoading(false);
    }
  };

  const loadPermissions = async () => {
    try {
      const response = await permissionsAPI.list();
      setPermissions(response.data.results || response.data || []);
    } catch (error) {
      console.error(error);
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
      <Layout>
        <PageLoading rows={6} />
      </Layout>
    );
  }

  return (
    <Layout>
      <PageShell>
        <PageHeader
          title="Roles"
          description="Group permissions for managers, sales staff, and custom jobs."
        >
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4" />
            Add role
          </Button>
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
            actionLabel="Add role"
            onAction={handleCreate}
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
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(role)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        disabled={role.is_system_role}
                        onClick={() => handleDelete(role)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
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
    </Layout>
  );
};

export default Roles;
