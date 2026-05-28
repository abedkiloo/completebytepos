import React, { useState, useEffect } from 'react';
import { Pencil, Plus, Trash2, Users as UsersIcon } from 'lucide-react';
import { usersAPI, rolesAPI } from '../../services/api';
import UserForm from './UserForm';
import SearchableSelect from '../Shared/SearchableSelect';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  FilterField,
  SearchField,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ActiveStatusBadge,
  SummaryCard,
} from '../page';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadUsers();
    loadRoles();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await usersAPI.list({ page_size: 1000 });
      const usersData = response.data.results || response.data || [];
      setUsers(Array.isArray(usersData) ? usersData : []);
    } catch (error) {
      toast.error(
        'Failed to load users: ' + (error.response?.data?.error || error.message)
      );
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

  const handleDelete = (user) => setPendingDelete(user);

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await usersAPI.delete(pendingDelete.id);
      toast.success('User deleted successfully');
      setPendingDelete(null);
      loadUsers();
    } catch (error) {
      toast.error(
        'Failed to delete user: ' + (error.response?.data?.error || error.message)
      );
    } finally {
      setDeleting(false);
    }
  };

  const handleAssignRole = async (user, roleId) => {
    try {
      await usersAPI.assignRole(user.id, roleId);
      toast.success('Role assigned successfully');
      loadUsers();
    } catch (error) {
      toast.error(
        'Failed to assign role: ' + (error.response?.data?.error || error.message)
      );
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setEditingUser(null);
    setSearchQuery('');
    setFilterRole('all');
    setFilterStatus('all');
    setTimeout(loadUsers, 200);
  };

  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      !searchQuery ||
      user.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.first_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.last_name?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesRole =
      filterRole === 'all' ||
      user.profile?.role === filterRole ||
      user.profile?.custom_role?.id === parseInt(filterRole, 10);

    const matchesStatus =
      filterStatus === 'all' ||
      (filterStatus === 'active' && user.is_active && user.profile?.is_active) ||
      (filterStatus === 'inactive' &&
        (!user.is_active || !user.profile?.is_active));

    return matchesSearch && matchesRole && matchesStatus;
  });

  const activeCount = users.filter((u) => u.is_active && u.profile?.is_active).length;

  if (loading) {
    return (
      <PageLoading rows={6} showStats />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Users"
          description="Manage who can sign in and what they can do in the store."
        >
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4" />
            Add user
          </Button>
        </PageHeader>

        <div className="grid gap-3 sm:grid-cols-2">
          <SummaryCard
            icon={UsersIcon}
            label="Total users"
            value={users.length.toLocaleString()}
          />
          <SummaryCard
            icon={UsersIcon}
            label="Active"
            value={activeCount.toLocaleString()}
            tone="success"
          />
        </div>

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by name, email, username…"
            className="min-w-[220px] flex-[2]"
          />
          <FilterField label="Role">
            <SearchableSelect
              value={filterRole}
              onChange={(e) => setFilterRole(e.target.value)}
              options={[
                { id: 'all', name: 'All roles' },
                { id: 'super_admin', name: 'Super Admin' },
                { id: 'manager', name: 'Manager' },
                { id: 'cashier', name: 'Cashier' },
                ...roles.map((role) => ({ id: role.id, name: role.name })),
              ]}
              placeholder="All roles"
            />
          </FilterField>
          <FilterField label="Status">
            <SearchableSelect
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              options={[
                { id: 'all', name: 'All status' },
                { id: 'active', name: 'Active' },
                { id: 'inactive', name: 'Inactive' },
              ]}
              placeholder="All status"
            />
          </FilterField>
        </FilterBar>

        {filteredUsers.length === 0 ? (
          <EmptyState
            icon={UsersIcon}
            title="No users found"
            description="Adjust filters or add a new team member."
            actionLabel="Add user"
            onAction={handleCreate}
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Username</DataTableHead>
              <DataTableHead>Name</DataTableHead>
              <DataTableHead>Email</DataTableHead>
              <DataTableHead>Role</DataTableHead>
              <DataTableHead>Status</DataTableHead>
              <DataTableHead>Joined</DataTableHead>
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {filteredUsers.map((user) => (
                <DataTableRow key={user.id}>
                  <DataTableCell className="font-medium">{user.username}</DataTableCell>
                  <DataTableCell>
                    {[user.first_name, user.last_name].filter(Boolean).join(' ') || '—'}
                  </DataTableCell>
                  <DataTableCell className="text-muted-foreground">
                    {user.email || '—'}
                  </DataTableCell>
                  <DataTableCell>
                    <SearchableSelect
                      value={
                        user.profile?.custom_role?.id || user.profile?.role || ''
                      }
                      onChange={(e) => {
                        const roleId = e.target.value;
                        if (roleId && roleId !== user.profile?.role) {
                          handleAssignRole(user, roleId);
                        }
                      }}
                      className="role-select max-w-[160px]"
                      options={[
                        { id: 'super_admin', name: 'Super Admin' },
                        { id: 'manager', name: 'Manager' },
                        { id: 'cashier', name: 'Cashier' },
                        ...roles.map((role) => ({ id: role.id, name: role.name })),
                      ]}
                      placeholder="Select role"
                    />
                  </DataTableCell>
                  <DataTableCell>
                    <ActiveStatusBadge
                      active={user.is_active && user.profile?.is_active}
                    />
                  </DataTableCell>
                  <DataTableCell className="text-muted-foreground">
                    {user.date_joined
                      ? new Date(user.date_joined).toLocaleDateString()
                      : '—'}
                  </DataTableCell>
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(user)}
                        disabled={user.is_superuser}
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
          <UserForm user={editingUser} roles={roles} onClose={handleFormClose} />
        )}

        <ConfirmDialog
          isOpen={!!pendingDelete}
          title="Delete user"
          message={
            pendingDelete
              ? `Remove "${pendingDelete.username}"? This cannot be undone.`
              : ''
          }
          confirmText="Delete user"
          cancelText="Cancel"
          type="danger"
          busy={deleting}
          onConfirm={confirmDelete}
          onCancel={() => (deleting ? null : setPendingDelete(null))}
        />
      </PageShell>
  );
};

export default Users;
