import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Pencil, Plus, Trash2, Users } from 'lucide-react';

import { payrollAPI, rolesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';

function unwrapList(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function basicSourceLabel(source) {
  if (source === 'assignment') return 'Personal BASIC override';
  if (source === 'employee.salary') return 'Employee salary';
  if (source === 'role_package') return 'Package BASIC line';
  if (source === 'role_package.default_basic') return 'Package default basic';
  return '—';
}

/**
 * Default pay package per job role. Everyone on that role inherits it;
 * Staff pay edits one person without changing the role package.
 */
export default function RolePackagesPanel({ components = [], onEditEmployee }) {
  const [roles, setRoles] = useState([]);
  const [packages, setPackages] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [pkg, setPkg] = useState(null);
  const [staffInfo, setStaffInfo] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [defaultBasic, setDefaultBasic] = useState('');
  const [lineForm, setLineForm] = useState({ component: '', amount: '', notes: '' });

  const activeComponents = useMemo(
    () =>
      (components || []).filter(
        (c) =>
          c.is_active &&
          !['BONUS_APPRAISAL', 'DED_LOAN', 'DED_ABSENCE'].includes(c.code)
      ),
    [components]
  );

  const loadOverview = useCallback(async (roleId = '') => {
    setOverviewLoading(true);
    try {
      const params = roleId ? { role: roleId } : {};
      const res = await payrollAPI.packageStaffOverview(params);
      setOverview(res.data);
    } catch {
      setOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [rolesRes, pkgRes] = await Promise.all([
        rolesAPI.list({ page_size: 100 }),
        payrollAPI.listPackages({ page_size: 100 }),
      ]);
      setRoles(unwrapList(rolesRes.data).filter((r) => r.is_active !== false));
      setPackages(unwrapList(pkgRes.data));
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not load packages');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    loadOverview('');
  }, [refresh, loadOverview]);

  const packageForRole = useCallback(
    (roleId) => packages.find((p) => String(p.role) === String(roleId)) || null,
    [packages]
  );

  const loadStaff = useCallback(async (packageId) => {
    if (!packageId) {
      setStaffInfo(null);
      return;
    }
    try {
      const res = await payrollAPI.packageStaff(packageId);
      setStaffInfo(res.data);
    } catch {
      setStaffInfo(null);
    }
  }, []);

  const selectRole = async (roleId) => {
    setSelectedRoleId(roleId);
    setStaffInfo(null);
    await loadOverview(roleId);
    const existing = packageForRole(roleId);
    if (existing) {
      try {
        const res = await payrollAPI.getPackage(existing.id);
        setPkg(res.data);
        setDefaultBasic(
          res.data.default_basic != null ? String(res.data.default_basic) : ''
        );
        await loadStaff(res.data.id);
      } catch {
        setPkg(existing);
        setDefaultBasic(
          existing.default_basic != null ? String(existing.default_basic) : ''
        );
        await loadStaff(existing.id);
      }
      return;
    }
    setPkg(null);
    setDefaultBasic('');
  };

  const ensurePackage = async () => {
    if (!selectedRoleId) {
      toast.error('Select a job role first');
      return null;
    }
    if (pkg?.id) return pkg;
    setBusy(true);
    try {
      const role = roles.find((r) => String(r.id) === String(selectedRoleId));
      const res = await payrollAPI.createPackage({
        role: Number(selectedRoleId),
        name: `${role?.name || 'Role'} package`,
        default_basic: defaultBasic === '' ? null : defaultBasic,
        is_active: true,
      });
      setPkg(res.data);
      await refresh();
      await loadStaff(res.data.id);
      await loadOverview(selectedRoleId);
      toast.success(
        'Role package created — every employee on this role inherits it on calculate'
      );
      return res.data;
    } catch (err) {
      toast.error(err?.response?.data?.detail || err?.response?.data?.role?.[0] || 'Create failed');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const savePackageMeta = async () => {
    const current = await ensurePackage();
    if (!current?.id) return;
    setBusy(true);
    try {
      const res = await payrollAPI.updatePackage(current.id, {
        default_basic: defaultBasic === '' ? null : defaultBasic,
        is_active: true,
      });
      setPkg(res.data);
      toast.success('Package saved — applies to all staff on this role');
      await refresh();
      await loadStaff(res.data.id);
      await loadOverview(selectedRoleId);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setBusy(false);
    }
  };

  const addLine = async (e) => {
    e.preventDefault();
    const current = await ensurePackage();
    if (!current?.id || !lineForm.component) {
      toast.error('Choose a component');
      return;
    }
    setBusy(true);
    try {
      const res = await payrollAPI.addPackageLine(current.id, {
        component: Number(lineForm.component),
        amount: lineForm.amount === '' ? null : lineForm.amount,
        notes: lineForm.notes || '',
        is_active: true,
      });
      setPkg(res.data);
      setLineForm({ component: '', amount: '', notes: '' });
      toast.success('Added for everyone on this role');
      await refresh();
      await loadStaff(res.data.id);
      await loadOverview(selectedRoleId);
    } catch (err) {
      toast.error(
        err?.response?.data?.detail ||
          err?.response?.data?.non_field_errors?.[0] ||
          'Could not add line'
      );
    } finally {
      setBusy(false);
    }
  };

  const toggleLine = async (line) => {
    setBusy(true);
    try {
      await payrollAPI.updatePackageLine(line.id, { is_active: !line.is_active });
      const res = await payrollAPI.getPackage(pkg.id);
      setPkg(res.data);
      await loadStaff(pkg.id);
      await loadOverview(selectedRoleId);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Update failed');
    } finally {
      setBusy(false);
    }
  };

  const removeLine = async (lineId) => {
    setBusy(true);
    try {
      await payrollAPI.deletePackageLine(lineId);
      const res = await payrollAPI.getPackage(pkg.id);
      setPkg(res.data);
      toast.success('Removed from role package');
      await loadStaff(pkg.id);
      await loadOverview(selectedRoleId);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Delete failed');
    } finally {
      setBusy(false);
    }
  };

  const usedComponentIds = useMemo(
    () => new Set((pkg?.lines || []).map((l) => l.component)),
    [pkg]
  );

  const availableLines = activeComponents.filter((c) => !usedComponentIds.has(c.id));
  const selectedRole = roles.find((r) => String(r.id) === String(selectedRoleId));
  const staffRows = overview?.results || [];

  if (loading) {
    return (
      <div className="flex justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading role packages…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground max-w-2xl">
        Current pay for every employee (active or not) comes from their role package
        plus any personal Staff-pay edits. Select a role below to edit that package.
      </p>

      <div className="space-y-3 rounded-lg border border-border/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Users className="h-4 w-4" />
            {selectedRoleId
              ? `Staff on ${selectedRole?.name || 'role'}`
              : 'All employees — current pay'}
          </div>
          {overview ? (
            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>{overview.employee_count} people</span>
              <span>Basic total {formatCurrency(overview.basic_total || 0)}</span>
              <span>Gross total {formatCurrency(overview.gross_total || 0)}</span>
            </div>
          ) : null}
        </div>

        {overviewLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading staff pay…
          </div>
        ) : staffRows.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">
            No employees yet. Add staff under Employees and assign a job role so they
            pick up a package.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-2">Employee</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">Role / package</th>
                  <th className="py-2 pr-2">Basic</th>
                  <th className="py-2 pr-2">Current gross</th>
                  <th className="py-2 pr-2">Source</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {staffRows.map((emp) => (
                  <tr key={emp.id} className="border-b border-border/40">
                    <td className="py-2 pr-2">
                      <div className="font-medium">{emp.full_name}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {emp.employee_id}
                        {emp.position ? ` · ${emp.position}` : ''}
                      </div>
                    </td>
                    <td className="py-2 pr-2">
                      <Badge
                        variant={emp.status === 'active' ? 'secondary' : 'outline'}
                      >
                        {emp.status || '—'}
                      </Badge>
                    </td>
                    <td className="py-2 pr-2">
                      <div>{emp.role_name || 'No role'}</div>
                      <div className="text-xs text-muted-foreground">
                        {emp.package_name || 'No package'}
                        {emp.override_count > 0
                          ? ` · ${emp.override_count} personal edit${
                              emp.override_count === 1 ? '' : 's'
                            }`
                          : ''}
                      </div>
                    </td>
                    <td className="py-2 pr-2 tabular-nums">
                      {formatCurrency(emp.effective_basic || 0)}
                    </td>
                    <td className="py-2 pr-2 tabular-nums font-medium">
                      {formatCurrency(emp.estimated_gross || 0)}
                    </td>
                    <td className="py-2 pr-2 text-xs text-muted-foreground">
                      {basicSourceLabel(emp.basic_source)}
                    </td>
                    <td className="py-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onEditEmployee?.(emp.id)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        Edit individual
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="max-w-md space-y-2">
        <Label htmlFor="pkg-role">Edit package for job role</Label>
        <select
          id="pkg-role"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={selectedRoleId}
          onChange={(e) => selectRole(e.target.value)}
        >
          <option value="">All roles (overview only)…</option>
          {roles.map((r) => {
            const has = packageForRole(r.id);
            return (
              <option key={r.id} value={r.id}>
                {r.name}
                {has ? ' · has package' : ''}
              </option>
            );
          })}
        </select>
      </div>

      {selectedRoleId ? (
        <div className="space-y-4 rounded-lg border border-border/60 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">
              {selectedRole?.name || 'Role'} package
            </h3>
            {pkg ? (
              <Badge variant="secondary">Active for role</Badge>
            ) : (
              <Badge variant="outline">Not created yet</Badge>
            )}
          </div>

          {staffInfo ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border bg-muted/20 px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Staff on role</div>
                <div className="text-lg font-semibold tabular-nums">
                  {staffInfo.employee_count}
                </div>
              </div>
              <div className="rounded-md border bg-muted/20 px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">
                  Basic pay total
                </div>
                <div className="text-lg font-semibold tabular-nums">
                  {formatCurrency(staffInfo.salary_total || 0)}
                </div>
              </div>
              <div className="rounded-md border bg-muted/20 px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">
                  Current gross total
                </div>
                <div className="text-lg font-semibold tabular-nums">
                  {formatCurrency(staffInfo.gross_total || 0)}
                </div>
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="pkg-basic">Default basic (KES)</Label>
              <Input
                id="pkg-basic"
                type="number"
                step="0.01"
                min="0"
                className="w-40"
                value={defaultBasic}
                onChange={(e) => setDefaultBasic(e.target.value)}
                placeholder="If employee salary empty"
              />
            </div>
            <Button type="button" size="sm" onClick={savePackageMeta} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {pkg ? 'Save package' : 'Create package'}
            </Button>
          </div>

          {pkg?.lines?.length ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-2">Component</th>
                  <th className="py-2 pr-2">Kind</th>
                  <th className="py-2 pr-2">Amount</th>
                  <th className="py-2 pr-2">Active</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {pkg.lines.map((line) => (
                  <tr key={line.id} className="border-b border-border/40">
                    <td className="py-2 pr-2">
                      <div className="font-medium">{line.component_name}</div>
                      <div className="font-mono text-xs text-muted-foreground">
                        {line.component_code}
                      </div>
                    </td>
                    <td className="py-2 pr-2">{line.component_kind}</td>
                    <td className="py-2 pr-2">
                      {line.amount != null ? formatCurrency(line.amount) : 'template default'}
                    </td>
                    <td className="py-2 pr-2">
                      <label className="inline-flex items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          checked={Boolean(line.is_active)}
                          disabled={busy}
                          onChange={() => toggleLine(line)}
                        />
                        {line.is_active ? 'On' : 'Off'}
                      </label>
                    </td>
                    <td className="py-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={() => removeLine(line.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">
              No lines yet — add allowances or deductions for this role below. They
              apply to every employee on the role until you override one person.
            </p>
          )}

          <form
            onSubmit={addLine}
            className="grid gap-3 rounded-md border border-dashed p-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="sm:col-span-2">
              <Label>Add to this role package</Label>
              <select
                className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={lineForm.component}
                onChange={(e) => setLineForm({ ...lineForm, component: e.target.value })}
                required
              >
                <option value="">Choose component…</option>
                {availableLines.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name} ({c.kind})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Amount</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={lineForm.amount}
                onChange={(e) => setLineForm({ ...lineForm, amount: e.target.value })}
                placeholder="e.g. 3000"
              />
            </div>
            <div>
              <Label>Notes</Label>
              <Input
                value={lineForm.notes}
                onChange={(e) => setLineForm({ ...lineForm, notes: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2 lg:col-span-4">
              <Button type="submit" size="sm" disabled={busy || !availableLines.length}>
                <Plus className="h-4 w-4" />
                Add line for whole role
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
