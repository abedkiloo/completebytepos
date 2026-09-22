import React, { useState, useEffect } from 'react';
import { Pencil, Plus, Trash2, Users as UsersIcon } from 'lucide-react';
import { usersAPI, rolesAPI } from '../../services/api';
import UserForm from './UserForm';
import SearchableSelect from '../Shared/SearchableSelect';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import CommitConfirm from '../Shared/CommitConfirm';
import { assignRoleRows } from '../../utils/formCommitSummary';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import {
  usersShowEmail,
  usersShowPhone,
  usersShowFullName,
  usersShowStatus,
  usersShowDateJoined,
  usersShowStatistics,
  usersShowStaffFlag,
  usersEnableCreate,
  usersEnableEdit,
  usersEnableDelete,
  usersEnableInlineRoleAssignment,
} from '../../utils/userDisplay';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
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
  const { settings } = useStoreSettings();
  const { settings: userSettings } = useModuleSettings('users');
  const hideStatusToggles = settings.hide_entity_status_toggles;
  const showEmail = usersShowEmail(userSettings);
  const showFullName = usersShowFullName(userSettings);
  const showStatus = usersShowStatus(userSettings, settings);
  const showDateJoined = usersShowDateJoined(userSettings);
  const showStats = usersShowStatistics(userSettings);
  const canCreate = usersEnableCreate(userSettings);
  const canEdit = usersEnableEdit(userSettings);
  const canDelete = usersEnableDelete(userSettings);
  const canAssignRole = usersEnableInlineRoleAssignment(userSettings);
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
  const [pendingRole, setPendingRole] = useState(null);
  const [assigningRole, setAssigningRole] = useState(false);

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

  const requestAssignRole = (user, roleId, roleLabel) => {
    if (!roleId || roleId === user.profile?.role) return;
    setPendingRole({ user, roleId, roleLabel });
  };

  const confirmAssignRole = async () => {
    if (!pendingRole) return;
    setAssigningRole(true);
    try {
      await usersAPI.assignRole(pendingRole.user.id, pendingRole.roleId);
      toast.success('Role assigned successfully');
      setPendingRole(null);
      loadUsers();
    } catch (error) {
      toast.error(
        'Failed to assign role: ' + (error.response?.data?.error || error.message)
      );
    } finally {
      setAssigningRole(false);
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
          {canCreate ? (
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4" />
            Add user
          </Button>
          ) : null}
        </PageHeader>

        {showStats ? (
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
        ) : null}

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
          {showStatus ? (
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
          ) : null}
        </FilterBar>

        {filteredUsers.length === 0 ? (
          <EmptyState
            icon={UsersIcon}
            title="No users found"
            description="Adjust filters or add a new team member."
            actionLabel={canCreate ? 'Add user' : undefined}
            onAction={canCreate ? handleCreate : undefined}
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Username</DataTableHead>
              {showFullName ? <DataTableHead>Name</DataTableHead> : null}
              {showEmail ? <DataTableHead>Email</DataTableHead> : null}
              <DataTableHead>Role</DataTableHead>
              {showStatus ? <DataTableHead>Status</DataTableHead> : null}
              {showDateJoined ? <DataTableHead>Joined</DataTableHead> : null}
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {filteredUsers.map((user) => (
                <DataTableRow key={user.id}>
                  <DataTableCell className="font-medium">
                    <div className="flex flex-col gap-1">
                      <span>{user.username}</span>
                      {user.profile?.must_change_password ? (
                        <Badge variant="warning" className="w-fit font-medium">
                          Must change on login
                        </Badge>
                      ) : null}
                    </div>
                  </DataTableCell>
                  {showFullName ? (
                  <DataTableCell>
                    {[user.first_name, user.last_name].filter(Boolean).join(' ') || '—'}
                  </DataTableCell>
                  ) : null}
                  {showEmail ? (
                  <DataTableCell className="text-muted-foreground">
                    {user.email || '—'}
                  </DataTableCell>
                  ) : null}
                  <DataTableCell>
                    {canAssignRole ? (
                    <SearchableSelect
                      value={
                        user.profile?.custom_role?.id || user.profile?.role || ''
                      }
                      onChange={(e) => {
                        const roleId = e.target.value;
                        const option = [
                          { id: 'super_admin', name: 'Super Admin' },
                          { id: 'manager', name: 'Manager' },
                          { id: 'cashier', name: 'Cashier' },
                          ...roles.map((role) => ({ id: role.id, name: role.name })),
                        ].find((opt) => String(opt.id) === String(roleId));
                        requestAssignRole(user, roleId, option?.name || roleId);
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
                    ) : (
                      user.profile?.custom_role?.name ||
                      user.profile?.role_display ||
                      user.profile?.role ||
                      '—'
                    )}
                  </DataTableCell>
                  {showStatus ? (
                  <DataTableCell>
                    <ActiveStatusBadge
                      active={user.is_active && user.profile?.is_active}
                    />
                  </DataTableCell>
                  ) : null}
                  {showDateJoined ? (
                  <DataTableCell className="text-muted-foreground">
                    {user.date_joined
                      ? new Date(user.date_joined).toLocaleDateString()
                      : '—'}
                  </DataTableCell>
                  ) : null}
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      {canEdit ? (
                      <Button variant="ghost" size="sm" onClick={() => handleEdit(user)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      ) : null}
                      {canDelete ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(user)}
                        disabled={user.is_superuser}
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
          <UserForm
            user={editingUser}
            roles={roles}
            onClose={handleFormClose}
            hideStatusToggles={hideStatusToggles || !showStatus}
            showEmail={showEmail}
            showFullName={showFullName}
            showPhone={usersShowPhone(userSettings)}
            showStaffFlag={usersShowStaffFlag(userSettings)}
            showInlineRoles={canAssignRole}
          />
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
        <CommitConfirm
          open={!!pendingRole}
          onOpenChange={(open) => {
            if (!open && !assigningRole) setPendingRole(null);
          }}
          title="Change this user's role?"
          description="They will get the new permissions immediately."
          rows={assignRoleRows(pendingRole?.user, pendingRole?.roleLabel)}
          submitting={assigningRole}
          confirmText="Confirm & assign"
          onConfirm={confirmAssignRole}
          variant="warning"
        />
      </PageShell>
  );
};

export default Users;
