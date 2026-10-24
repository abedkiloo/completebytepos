import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import {
  Eye,
  Loader2,
  Pencil,
  Plus,
  Search,
  Trash2,
  UserCog,
  X,
} from 'lucide-react';

import { employeesAPI, rolesAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import CommitConfirm from '../Shared/CommitConfirm';
import { employeeCommitRows } from '../../utils/formCommitSummary';
import {
  dateMessage,
  emailMessage,
  moneyMessage,
  personNameMessage,
  phoneMessage,
  required,
} from '../../utils/formValidation';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  employeesShowEmployeeId,
  employeesShowSalary,
  employeesShowDepartment,
  employeesShowContactDetails,
  employeesShowNotes,
  employeesShowStatus,
  employeesEnableCreate,
  employeesEnableEdit,
  employeesEnableDelete,
  employeesEnableStatistics,
} from '../../utils/employeeDisplay';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { cn } from '../../lib/cn';
import { PageShell, PageHeader, ListPaginationRail } from '../page';
import { useListOrdering } from '../../hooks/useListOrdering';
import { withListOrdering } from '../../utils/listOrdering';
import { SortableHeadButton } from '../page/ListSortBar';

const DEPARTMENTS = [
  { value: 'production', label: 'Production' },
  { value: 'sales', label: 'Sales' },
  { value: 'admin', label: 'Administration' },
  { value: 'finance', label: 'Finance' },
  { value: 'management', label: 'Management' },
  { value: 'other', label: 'Other' },
];

const STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'on_leave', label: 'On leave' },
  { value: 'terminated', label: 'Terminated' },
];

const EMPTY_FORM = {
  employee_id: '',
  id_number: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  role_id: '',
  position: '',
  department: 'other',
  hire_date: '',
  status: 'active',
  salary: '',
  address: '',
  notes: '',
};

export default function Employees() {
  const { settings: employeeSettings } = useModuleSettings('employees');
  const { settings: storeSettings } = useStoreSettings();

  const showEmployeeId = employeesShowEmployeeId(employeeSettings);
  const showSalary = employeesShowSalary(employeeSettings);
  const showDepartment = employeesShowDepartment(employeeSettings);
  const showContact = employeesShowContactDetails(employeeSettings);
  const showNotes = employeesShowNotes(employeeSettings);
  const showStatus = employeesShowStatus(employeeSettings, storeSettings);
  const canCreate = employeesEnableCreate(employeeSettings);
  const canEdit = employeesEnableEdit(employeeSettings);
  const canDelete = employeesEnableDelete(employeeSettings);
  const showStats = employeesEnableStatistics(employeeSettings);

  const [employees, setEmployees] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebouncedValue(searchQuery);
  const [statusFilter, setStatusFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [detailEmp, setDetailEmp] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [createMode, setCreateMode] = useState('manual'); // manual | from_user
  const [linkableUsers, setLinkableUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });
  const { ordering, setOrdering } = useListOrdering();

  const listFilterParams = useCallback(() => {
    const params = {};
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
    if (statusFilter) params.status = statusFilter;
    if (roleFilter) params.role = roleFilter;
    return params;
  }, [debouncedSearch, statusFilter, roleFilter]);

  const loadEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const params = withListOrdering({
        page: pagination.page,
        page_size: pagination.page_size,
        ...listFilterParams(),
      }, ordering);
      const res = await employeesAPI.list(params);
      const data = res.data.results || res.data || [];
      setEmployees(Array.isArray(data) ? data : []);
      setPagination((prev) => ({
        ...prev,
        count: res.data?.count ?? (Array.isArray(data) ? data.length : 0),
      }));
    } catch {
      toast.error('Failed to load employees');
      setEmployees([]);
    } finally {
      setLoading(false);
    }
  }, [listFilterParams, pagination.page, pagination.page_size, ordering]);

  useEffect(() => {
    setPagination((prev) => (prev.page === 1 ? prev : { ...prev, page: 1 }));
  }, [debouncedSearch, statusFilter, roleFilter]);

  const loadStatistics = useCallback(async () => {
    if (!showStats) {
      setStatistics(null);
      return;
    }
    try {
      const res = await employeesAPI.statistics(listFilterParams());
      setStatistics(res.data);
    } catch {
      setStatistics(null);
    }
  }, [showStats, listFilterParams]);

  const loadRoles = useCallback(async () => {
    try {
      const res = await rolesAPI.list({ page_size: 100 });
      const data = res.data?.results || res.data || [];
      setRoles(Array.isArray(data) ? data.filter((r) => r.is_active !== false) : []);
    } catch {
      setRoles([]);
    }
  }, []);

  useEffect(() => {
    loadEmployees();
    loadStatistics();
  }, [loadEmployees, loadStatistics]);

  useEffect(() => {
    loadRoles();
  }, [loadRoles]);

  const loadLinkableUsers = useCallback(async () => {
    try {
      const res = await employeesAPI.linkableUsers();
      setLinkableUsers(res.data?.results || []);
    } catch {
      setLinkableUsers([]);
    }
  }, []);

  const openCreate = () => {
    setEditing(null);
    setCreateMode('from_user');
    setSelectedUserId('');
    setFormData({
      ...EMPTY_FORM,
      hire_date: new Date().toISOString().slice(0, 10),
    });
    setShowModal(true);
    loadLinkableUsers();
  };

  const openEdit = (emp) => {
    setDetailEmp(null);
    setEditing(emp);
    setCreateMode('manual');
    setSelectedUserId('');
    setFormData({
      employee_id: emp.employee_id || '',
      id_number: emp.id_number || '',
      first_name: emp.first_name || '',
      last_name: emp.last_name || '',
      email: emp.email || emp.user_email || '',
      phone: emp.phone || '',
      role_id: emp.role_id != null ? String(emp.role_id) : '',
      position: emp.position || '',
      department: emp.department || 'other',
      hire_date: emp.hire_date || '',
      status: emp.status || 'active',
      salary: emp.salary != null ? String(emp.salary) : '',
      address: emp.address || '',
      notes: emp.notes || '',
    });
    setShowModal(true);
  };

  const hasLinkedUser = Boolean(
    (editing && (editing.user || editing.user_username)) ||
      (!editing && createMode === 'from_user' && selectedUserId)
  );

  const applyRoleSelection = (roleId) => {
    const role = roles.find((r) => String(r.id) === String(roleId));
    setFormData((prev) => ({
      ...prev,
      role_id: roleId,
      position: role ? role.name : prev.position,
    }));
  };

  const applySelectedUser = (userId) => {
    setSelectedUserId(userId);
    const u = linkableUsers.find((row) => String(row.id) === String(userId));
    if (!u) return;
    setFormData((prev) => ({
      ...prev,
      first_name: u.first_name || u.username || prev.first_name,
      last_name: u.last_name || 'User',
      email: u.email || '',
      employee_id: prev.employee_id || `USR-${u.id}`,
    }));
  };

  const buildPayload = () => {
    const payload = {
      employee_id: formData.employee_id.trim(),
      first_name: formData.first_name.trim(),
      last_name: formData.last_name.trim(),
      position: formData.position.trim(),
      hire_date: formData.hire_date,
    };
    if (hasLinkedUser) {
      payload.job_role_id =
        formData.role_id === '' ? null : Number(formData.role_id);
    }
    if (showContact) {
      payload.email = formData.email.trim();
      payload.id_number = formData.id_number.trim();
      payload.phone = formData.phone.trim();
      payload.address = formData.address.trim();
    }
    if (showDepartment) payload.department = formData.department;
    if (showStatus) payload.status = formData.status;
    // Always allow basic salary on create/edit — components stay optional in Payroll.
    if (formData.salary !== '') {
      payload.salary = parseFloat(formData.salary) || 0;
    } else if (editing) {
      payload.salary = null;
    }
    if (showNotes) payload.notes = formData.notes.trim();
    return payload;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!editing && createMode === 'from_user') {
      if (!selectedUserId) {
        toast.error('Select a login user to make an employee');
        return;
      }
      if (!formData.role_id && !formData.position.trim()) {
        toast.error('Select a position / job role');
        return;
      }
      const hireErr = dateMessage(formData.hire_date, { label: 'hire date' });
      if (hireErr) {
        toast.error(hireErr);
        return;
      }
      if (formData.salary !== '') {
        const salaryErr = moneyMessage(formData.salary, {
          allowZero: true,
          label: 'basic salary',
        });
        if (salaryErr) {
          toast.error(salaryErr);
          return;
        }
      }
      setShowCommitConfirm(true);
      return;
    }

    const firstErr = personNameMessage(formData.first_name, {
      label: 'first name',
      example: 'Jane',
      min: 1,
    });
    if (firstErr) {
      toast.error(firstErr);
      return;
    }
    const lastErr = personNameMessage(formData.last_name, {
      label: 'last name',
      example: 'Wambua',
      min: 1,
    });
    if (lastErr) {
      toast.error(lastErr);
      return;
    }
    const idErr = required(formData.employee_id, 'Enter employee ID, e.g. EMP-0042');
    if (idErr) {
      toast.error(idErr);
      return;
    }
    if (!formData.role_id && !formData.position.trim()) {
      toast.error('Select a position / job role');
      return;
    }
    const hireErr = dateMessage(formData.hire_date, { label: 'hire date' });
    if (hireErr) {
      toast.error(hireErr);
      return;
    }
    if (showContact) {
      const emailErr = emailMessage(formData.email);
      if (emailErr) {
        toast.error(emailErr);
        return;
      }
      const phoneErr = phoneMessage(formData.phone);
      if (phoneErr) {
        toast.error(phoneErr);
        return;
      }
    }
    if (formData.salary !== '') {
      const salaryErr = moneyMessage(formData.salary, {
        allowZero: true,
        label: 'basic salary',
      });
      if (salaryErr) {
        toast.error(salaryErr);
        return;
      }
    }
    setShowCommitConfirm(true);
  };

  const confirmCommit = async () => {
    if (saving) return;
    setSaving(true);
    try {
      if (!editing && createMode === 'from_user') {
        await employeesAPI.createFromUser({
          user_id: Number(selectedUserId),
          employee_id: formData.employee_id.trim() || undefined,
          id_number: formData.id_number.trim() || '',
          email: formData.email.trim() || undefined,
          role_id: formData.role_id === '' ? null : Number(formData.role_id),
          job_role_id: formData.role_id === '' ? null : Number(formData.role_id),
          position: formData.position.trim(),
          department: formData.department || 'other',
          hire_date: formData.hire_date,
          salary: formData.salary === '' ? null : parseFloat(formData.salary) || 0,
          status: formData.status || 'active',
          notes: formData.notes.trim(),
        });
        toast.success('Login user added as employee');
      } else {
        const payload = buildPayload();
        if (editing) {
          await employeesAPI.update(editing.id, payload);
          toast.success('Employee updated');
        } else {
          await employeesAPI.create(payload);
          toast.success('Employee created');
        }
      }
      setShowCommitConfirm(false);
      setShowModal(false);
      loadEmployees();
      loadStatistics();
    } catch (err) {
      const data = err.response?.data || {};
      const detail =
        data.error ||
        data.detail ||
        data.user_id?.[0] ||
        data.employee_id?.[0] ||
        'Save failed';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await employeesAPI.delete(pendingDelete.id);
      toast.success('Employee deleted');
      setPendingDelete(null);
      loadEmployees();
      loadStatistics();
    } catch (err) {
      toast.error(err.response?.data?.error || 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  const deptLabel = useMemo(
    () => Object.fromEntries(DEPARTMENTS.map((d) => [d.value, d.label])),
    []
  );

  return (
    <PageShell>
      <PageHeader
        title="Employees"
        description="Staff records with pay. Filter by role to see that team’s headcount and salary total."
      >
        {canCreate && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Add employee
          </Button>
        )}
      </PageHeader>

      {showStats && statistics && (
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label={roleFilter ? 'In this role' : 'Total staff'}
            value={statistics.total_employees}
          />
          <StatCard label="Active" value={statistics.active_employees} tone="success" />
          <StatCard label="Inactive" value={statistics.inactive_employees} />
          {showSalary ? (
            <StatCard
              label={roleFilter ? 'Role salary total' : 'Salary total'}
              value={formatCurrency(statistics.total_salary || 0)}
            />
          ) : null}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative min-w-[200px] flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search name, staff code, ID number, email…"
            className="h-10 pl-9"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              aria-label="Clear"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        {showStatus && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        )}
      </div>

      <ListPaginationRail
        page={pagination.page}
        pageSize={pagination.page_size}
        totalCount={pagination.count}
        suffix={`${pagination.count} employees`}
        ordering={ordering}
        onOrderingChange={setOrdering}
        onPageChange={(nextPage) =>
          setPagination((prev) => ({ ...prev, page: nextPage }))
        }
      >
      <div className="overflow-hidden rounded-lg border bg-background">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium">
                <SortableHeadButton
                  sortKey="name"
                  ordering={ordering}
                  onOrderingChange={setOrdering}
                >
                  Employee
                </SortableHeadButton>
              </th>
              {showEmployeeId && (
                <th className="px-4 py-2.5 text-left font-medium" title="Internal staff code (not national ID)">
                  Staff code
                </th>
              )}
              {showContact && (
                <th className="px-4 py-2.5 text-left font-medium" title="National ID / passport">
                  ID number
                </th>
              )}
              <th className="px-4 py-2.5 text-left font-medium">Role</th>
              <th className="px-4 py-2.5 text-left font-medium">Position</th>
              {showDepartment && <th className="px-4 py-2.5 text-left font-medium">Dept</th>}
              {showSalary && <th className="px-4 py-2.5 text-right font-medium">Basic pay</th>}
              {showStatus && <th className="px-4 py-2.5 text-left font-medium">Status</th>}
              <th className="px-4 py-2.5 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading && employees.length === 0 ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 8 }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : employees.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                  <UserCog className="mx-auto mb-2 h-8 w-8 opacity-40" />
                  No employees found
                  {canCreate && (
                    <div className="mt-3">
                      <Button size="sm" onClick={openCreate}>
                        Add employee
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ) : (
              employees.map((emp) => (
                <tr
                  key={emp.id}
                  className="hover:bg-muted/40 cursor-pointer"
                  onClick={() => setDetailEmp(emp)}
                >
                  <td className="px-4 py-3 font-medium">
                    {emp.full_name || `${emp.first_name} ${emp.last_name}`}
                    {emp.user_username ? (
                      <div className="text-xs font-normal text-muted-foreground">
                        Login: {emp.user_username}
                      </div>
                    ) : null}
                    {showContact && (emp.email || emp.user_email) ? (
                      <div className="text-xs font-normal text-muted-foreground">
                        {emp.email || emp.user_email}
                      </div>
                    ) : null}
                    {showContact && emp.phone ? (
                      <div className="text-xs font-normal text-muted-foreground">{emp.phone}</div>
                    ) : null}
                  </td>
                  {showEmployeeId && (
                    <td className="px-4 py-3 font-mono text-xs">
                      {emp.employee_id || '—'}
                    </td>
                  )}
                  {showContact && (
                    <td className="px-4 py-3 font-mono text-xs">
                      {emp.id_number || '—'}
                    </td>
                  )}
                  <td className="px-4 py-3 text-muted-foreground">
                    {emp.role_name || '—'}
                  </td>
                  <td className="px-4 py-3">{emp.position}</td>
                  {showDepartment && (
                    <td className="px-4 py-3 text-muted-foreground">
                      {deptLabel[emp.department] || emp.department}
                    </td>
                  )}
                  {showSalary && (
                    <td className="px-4 py-3 text-right tabular-nums">
                      {emp.salary != null ? formatCurrency(emp.salary) : '—'}
                    </td>
                  )}
                  {showStatus && (
                    <td className="px-4 py-3">
                      <Badge variant={emp.status === 'active' ? 'success' : 'outline'}>
                        {STATUSES.find((s) => s.value === emp.status)?.label || emp.status}
                      </Badge>
                    </td>
                  )}
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDetailEmp(emp)}
                        aria-label="View details"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                      {canEdit && (
                        <Button variant="ghost" size="sm" onClick={() => openEdit(emp)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => setPendingDelete(emp)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      </ListPaginationRail>

      <Dialog open={showModal} onOpenChange={(o) => !saving && setShowModal(o)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit employee' : 'Add employee'}</DialogTitle>
            <p className="text-sm text-muted-foreground pt-1">
              {editing
                ? 'Update employment details. Pay components stay optional under Payroll → Staff pay.'
                : 'Prefer selecting an existing login user. Or add a person who has no login yet. Only basic salary is required for payroll.'}
            </p>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-3">
            {!editing ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={createMode === 'from_user' ? 'default' : 'outline'}
                  onClick={() => {
                    setCreateMode('from_user');
                    loadLinkableUsers();
                  }}
                >
                  From login user
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={createMode === 'manual' ? 'default' : 'outline'}
                  onClick={() => setCreateMode('manual')}
                >
                  New person (no login)
                </Button>
              </div>
            ) : null}

            {!editing && createMode === 'from_user' ? (
              <Field label="Login user" required>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={selectedUserId}
                  onChange={(e) => applySelectedUser(e.target.value)}
                >
                  <option value="">Select user…</option>
                  {linkableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.username}
                      {u.full_name ? ` — ${u.full_name}` : ''}
                      {u.email ? ` (${u.email})` : ''}
                    </option>
                  ))}
                </select>
                {linkableUsers.length === 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    No unlinked users. Create a user under Users first, then return here.
                  </p>
                ) : null}
              </Field>
            ) : null}

            {(editing || createMode === 'manual') ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="First name" required>
                <Input
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                />
              </Field>
              <Field label="Last name" required>
                <Input
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                />
              </Field>
            </div>
            ) : null}

            <Field
              label="Staff code"
              required={editing || createMode === 'manual'}
              hint="Internal HR code (e.g. EMP-0042). Not the national ID."
            >
              <Input
                value={formData.employee_id}
                onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
                disabled={!!editing}
                placeholder={
                  createMode === 'from_user' && !editing
                    ? 'Optional — auto USR-{id} if blank'
                    : 'e.g. EMP-0042'
                }
              />
            </Field>
            {showContact ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Personal email" hint="Used for payslip self-service match">
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="name@example.com"
                  />
                </Field>
                <Field label="ID number" hint="National ID / passport">
                  <Input
                    value={formData.id_number}
                    onChange={(e) => setFormData({ ...formData, id_number: e.target.value })}
                    placeholder="e.g. 12345678"
                  />
                </Field>
              </div>
            ) : null}
            {hasLinkedUser ? (
              <Field
                label="Position / job role"
                required
                hint="Select Manager, Sales Personnel, etc. They inherit that role’s pay package."
              >
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={formData.role_id}
                  onChange={(e) => applyRoleSelection(e.target.value)}
                  required
                >
                  <option value="">Select position…</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <Field
                label="Position"
                required
                hint="To assign a pay-package role, create/link a login user for this employee first."
              >
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={
                    roles.some((r) => r.name === formData.position)
                      ? formData.position
                      : formData.position
                        ? '__custom__'
                        : ''
                  }
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === '__custom__') {
                      setFormData((prev) => ({
                        ...prev,
                        role_id: '',
                        position: prev.position && !roles.some((r) => r.name === prev.position)
                          ? prev.position
                          : '',
                      }));
                      return;
                    }
                    setFormData((prev) => ({
                      ...prev,
                      role_id: '',
                      position: v,
                    }));
                  }}
                  required
                >
                  <option value="">Select position…</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.name}>
                      {r.name}
                    </option>
                  ))}
                  <option value="__custom__">Other (type below)…</option>
                </select>
                {!roles.some((r) => r.name === formData.position) ? (
                  <Input
                    className="mt-2"
                    value={formData.position}
                    onChange={(e) =>
                      setFormData({ ...formData, position: e.target.value })
                    }
                    placeholder="e.g. Sales Consultant"
                  />
                ) : null}
              </Field>
            )}
            <Field label="Hire date" required>
              <Input
                type="date"
                value={formData.hire_date}
                onChange={(e) => setFormData({ ...formData, hire_date: e.target.value })}
              />
            </Field>
            <Field label="Monthly basic salary (KES)">
              <Input
                type="number"
                min="0"
                step="0.01"
                value={formData.salary}
                onChange={(e) => setFormData({ ...formData, salary: e.target.value })}
                placeholder="e.g. 25000"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Basic pay only. Extra allowances are optional under Payroll → Staff pay.
              </p>
            </Field>
            {showDepartment && (
              <Field label="Department">
                <select
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {DEPARTMENTS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {showStatus && (
              <Field label="Status">
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {showContact && (
              <>
                <Field label="Phone">
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </Field>
                <Field label="Address">
                  <Input
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  />
                </Field>
              </>
            )}
            {showNotes && (
              <Field label="Notes">
                <textarea
                  rows={2}
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </Field>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowModal(false)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? 'Save' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!detailEmp} onOpenChange={(open) => !open && setDetailEmp(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {detailEmp
                ? detailEmp.full_name ||
                  `${detailEmp.first_name} ${detailEmp.last_name}`
                : 'Employee'}
            </DialogTitle>
          </DialogHeader>
          {detailEmp ? (
            <div className="space-y-3 text-sm">
              <DetailRow label="Staff code" value={detailEmp.employee_id} mono />
              <DetailRow label="ID number" value={detailEmp.id_number || '—'} mono />
              <DetailRow
                label="Personal email"
                value={detailEmp.email || detailEmp.user_email || '—'}
              />
              <DetailRow label="Phone" value={detailEmp.phone || '—'} />
              <DetailRow label="Login user" value={detailEmp.user_username || '—'} />
              <DetailRow label="Role" value={detailEmp.role_name || '—'} />
              <DetailRow label="Position" value={detailEmp.position || '—'} />
              <DetailRow
                label="Department"
                value={deptLabel[detailEmp.department] || detailEmp.department || '—'}
              />
              <DetailRow
                label="Basic monthly pay"
                value={
                  detailEmp.salary != null ? formatCurrency(detailEmp.salary) : '—'
                }
              />
              <DetailRow
                label="Status"
                value={
                  STATUSES.find((s) => s.value === detailEmp.status)?.label ||
                  detailEmp.status
                }
              />
              <DetailRow label="Hire date" value={detailEmp.hire_date || '—'} />
              {detailEmp.address ? (
                <DetailRow label="Address" value={detailEmp.address} />
              ) : null}
              {detailEmp.notes ? (
                <DetailRow label="Notes" value={detailEmp.notes} />
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDetailEmp(null)}>
              Close
            </Button>
            {canEdit && detailEmp ? (
              <Button
                type="button"
                onClick={() => {
                  const emp = detailEmp;
                  openEdit(emp);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="Delete employee"
        message={pendingDelete ? `Remove ${pendingDelete.full_name || pendingDelete.first_name}?` : ''}
        confirmText="Delete"
        type="danger"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(open) => {
          if (!open && !saving) setShowCommitConfirm(false);
        }}
        title={editing ? 'Update this employee?' : 'Create this employee?'}
        description="Review the employee details, then confirm to save."
        rows={employeeCommitRows(formData, { isEdit: !!editing })}
        submitting={saving}
        confirmText={editing ? 'Confirm & update' : 'Confirm & create'}
        onConfirm={confirmCommit}
      />
    </PageShell>
  );
}

function StatCard({ label, value, tone = 'default' }) {
  return (
    <div className="rounded-lg border bg-background px-4 py-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div
        className={cn(
          'mt-1 text-xl font-semibold tabular-nums',
          tone === 'success' && 'text-success'
        )}
      >
        {value ?? 0}
      </div>
    </div>
  );
}

function DetailRow({ label, value, mono = false }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-2">
      <div className="text-muted-foreground">{label}</div>
      <div className={cn(mono && 'font-mono text-xs')}>{value}</div>
    </div>
  );
}

function Field({ label, required, hint, children }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">
        {label}
        {required && <span className="text-destructive"> *</span>}
      </Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
