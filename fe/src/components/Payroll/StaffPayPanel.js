import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';

import { employeesAPI, payrollAPI } from '../../services/api';
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

/**
 * Per-employee overrides on top of the role package.
 * Role package applies automatically; lines here win for this person only.
 */
export default function StaffPayPanel({
  components = [],
  initialEmployeeId = '',
}) {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState(
    initialEmployeeId ? String(initialEmployeeId) : ''
  );
  const [assignments, setAssignments] = useState([]);
  const [rolePackage, setRolePackage] = useState(null);
  const [payPreview, setPayPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    component: '',
    amount: '',
    rate: '',
    notes: '',
  });

  useEffect(() => {
    if (initialEmployeeId) {
      setEmployeeId(String(initialEmployeeId));
    }
  }, [initialEmployeeId]);

  const employee = useMemo(
    () => employees.find((e) => String(e.id) === String(employeeId)) || null,
    [employees, employeeId]
  );

  const assignableComponents = useMemo(
    () =>
      (components || []).filter(
        (c) =>
          c.is_active &&
          !c.is_statutory &&
          !['BONUS_APPRAISAL', 'DED_LOAN', 'DED_ABSENCE'].includes(c.code)
      ),
    [components]
  );

  const loadEmployees = useCallback(async () => {
    const res = await employeesAPI.list({ page_size: 200, status: 'active' });
    setEmployees(unwrapList(res.data));
  }, []);

  const loadAssignments = useCallback(async (id) => {
    if (!id) {
      setAssignments([]);
      return;
    }
    const res = await payrollAPI.listAssignments({ employee: id, page_size: 100 });
    setAssignments(unwrapList(res.data));
  }, []);

  const loadRolePackage = useCallback(async (emp) => {
    if (!emp) {
      setRolePackage(null);
      return;
    }
    try {
      let match = null;
      if (emp.role_id) {
        const res = await payrollAPI.listPackages({ role: emp.role_id, page_size: 5 });
        const rows = unwrapList(res.data);
        match = rows.find((p) => p.is_active !== false) || rows[0] || null;
      }
      if (!match && (emp.position || emp.role_name)) {
        const all = await payrollAPI.listPackages({ page_size: 100 });
        const rows = unwrapList(all.data);
        const needle = String(emp.role_name || emp.position || '')
          .trim()
          .toLowerCase();
        match =
          rows.find(
            (p) =>
              p.is_active !== false &&
              String(p.role_name || p.name || '')
                .trim()
                .toLowerCase() === needle
          ) || null;
      }
      if (match?.id) {
        const full = await payrollAPI.getPackage(match.id);
        setRolePackage(full.data);
      } else {
        setRolePackage(null);
      }
    } catch {
      setRolePackage(null);
    }
  }, []);

  const loadPayPreview = useCallback(async (id) => {
    if (!id) {
      setPayPreview(null);
      return;
    }
    try {
      const res = await payrollAPI.packageStaffOverview({ employee: id });
      const row = (res.data?.results || [])[0] || null;
      setPayPreview(row);
    } catch {
      setPayPreview(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await loadEmployees();
      } catch (err) {
        if (!cancelled) {
          toast.error(
            err?.response?.data?.detail ||
              'Could not load employees (need employees.view)'
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadEmployees]);

  useEffect(() => {
    loadAssignments(employeeId).catch(() => setAssignments([]));
    loadPayPreview(employeeId);
  }, [employeeId, loadAssignments, loadPayPreview]);

  useEffect(() => {
    loadRolePackage(employee);
  }, [employee, loadRolePackage]);

  const assignedIds = useMemo(
    () => new Set(assignments.map((a) => a.component)),
    [assignments]
  );

  const availableToAdd = useMemo(
    () => assignableComponents.filter((c) => !assignedIds.has(c.id)),
    [assignableComponents, assignedIds]
  );

  const saveAssignment = async (e) => {
    e.preventDefault();
    if (!employeeId || !form.component) {
      toast.error('Pick an employee and a pay component');
      return;
    }
    setBusy(true);
    try {
      const payload = {
        employee: Number(employeeId),
        component: Number(form.component),
        amount: form.amount === '' ? null : form.amount,
        rate: form.rate === '' ? null : form.rate,
        notes: form.notes || '',
        is_active: true,
      };
      await payrollAPI.createAssignment(payload);
      toast.success('Staff pay line saved');
      setForm({ component: '', amount: '', rate: '', notes: '' });
      await loadAssignments(employeeId);
      await loadPayPreview(employeeId);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors?.[0] ||
        'Could not save (need payroll.manage)';
      toast.error(typeof detail === 'string' ? detail : 'Could not save assignment');
    } finally {
      setBusy(false);
    }
  };

  const updateAmount = async (row, amount) => {
    setBusy(true);
    try {
      await payrollAPI.updateAssignment(row.id, {
        amount: amount === '' ? null : amount,
      });
      await loadAssignments(employeeId);
      await loadPayPreview(employeeId);
      toast.success('Updated');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Update failed');
    } finally {
      setBusy(false);
    }
  };

  const removeAssignment = async (id) => {
    setBusy(true);
    try {
      await payrollAPI.deleteAssignment(id);
      await loadAssignments(employeeId);
      await loadPayPreview(employeeId);
      toast.success('Removed');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Delete failed');
    } finally {
      setBusy(false);
    }
  };

  const inheritedLines = useMemo(
    () => (rolePackage?.lines || []).filter((l) => l.is_active),
    [rolePackage]
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading staff…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground max-w-2xl">
        If this person has a job role with a package, they already inherit those
        lines. Add or change amounts here only when this one employee should differ
        from the role package.
      </p>

      <div className="max-w-md space-y-2">
        <Label htmlFor="staff-pay-employee">Employee</Label>
        <select
          id="staff-pay-employee"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={employeeId}
          onChange={(ev) => setEmployeeId(ev.target.value)}
        >
          <option value="">Select staff…</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.employee_id} — {emp.full_name || `${emp.first_name} ${emp.last_name}`}
              {emp.role_name ? ` (${emp.role_name})` : ''}
            </option>
          ))}
        </select>
      </div>

      {employee ? (
        <div className="rounded-lg border border-border/60 p-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border bg-muted/20 px-3 py-2">
              <div className="text-xs uppercase text-muted-foreground">
                Current basic
              </div>
              <div className="text-lg font-semibold tabular-nums">
                {formatCurrency(
                  payPreview?.effective_basic ?? employee.salary ?? 0
                )}
              </div>
            </div>
            <div className="rounded-md border bg-muted/20 px-3 py-2">
              <div className="text-xs uppercase text-muted-foreground">
                Current gross
              </div>
              <div className="text-lg font-semibold tabular-nums">
                {formatCurrency(payPreview?.estimated_gross ?? 0)}
              </div>
            </div>
            <div className="rounded-md border bg-muted/20 px-3 py-2">
              <div className="text-xs uppercase text-muted-foreground">
                Current net (est.)
              </div>
              <div className="text-lg font-semibold tabular-nums">
                {formatCurrency(payPreview?.estimated_net ?? 0)}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Record salary </span>
              <strong>{formatCurrency(employee.salary || 0)}</strong>
            </div>
            <div>
              <span className="text-muted-foreground">Role </span>
              {payPreview?.role_name || employee.role_name || '—'}
            </div>
            <div>
              <span className="text-muted-foreground">Position </span>
              {employee.position || '—'}
            </div>
            <div>
              <span className="text-muted-foreground">Package </span>
              {payPreview?.package_name || rolePackage?.display_name || rolePackage?.name || '—'}
            </div>
          </div>

          {rolePackage ? (
            <div className="rounded-md border border-dashed bg-muted/20 p-3 space-y-2">
              <div className="text-sm font-medium">
                Inherited from {rolePackage.role_name || rolePackage.name} package
              </div>
              {inheritedLines.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Role package exists but has no active lines yet. Set default basic
                  and add allowances under Role packages.
                </p>
              ) : (
                <ul className="text-sm space-y-1">
                  {inheritedLines.map((line) => (
                    <li key={line.id} className="flex flex-wrap gap-2">
                      <span>{line.component_name}</span>
                      <span className="text-muted-foreground">
                        {line.amount != null
                          ? formatCurrency(line.amount)
                          : 'template default'}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        role
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted-foreground">
                Personal lines below override the same component for this employee
                only. Current gross above already includes role package + overrides.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No role package found for this person. Under Employees, set Position /
              job role to <strong>Sales Personnel</strong> (or their role), and create
              that Role package — or add personal lines here.
            </p>
          )}

          <div className="text-sm font-medium">Personal overrides (this employee)</div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-2">Component</th>
                  <th className="py-2 pr-2">Kind</th>
                  <th className="py-2 pr-2">Amount (KES)</th>
                  <th className="py-2 pr-2">Notes</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-muted-foreground">
                      No personal overrides — full role package applies as-is.
                    </td>
                  </tr>
                ) : (
                  assignments.map((row) => {
                    const comp = components.find((c) => c.id === row.component);
                    const kindLabel =
                      row.component_code === 'BASIC'
                        ? 'basic override'
                        : comp?.kind || '—';
                    return (
                    <tr key={row.id} className="border-b border-border/40">
                      <td className="py-2 pr-2">
                        <div className="font-medium">{row.component_name}</div>
                        <div className="font-mono text-xs text-muted-foreground">
                          {row.component_code}
                        </div>
                      </td>
                      <td className="py-2 pr-2">
                        <Badge variant="secondary">{kindLabel}</Badge>
                      </td>
                      <td className="py-2 pr-2">
                        <Input
                          className="w-32"
                          type="number"
                          step="0.01"
                          defaultValue={row.amount ?? ''}
                          placeholder="default"
                          onBlur={(ev) => {
                            const next = ev.target.value;
                            const prev = row.amount == null ? '' : String(row.amount);
                            if (next !== prev) updateAmount(row, next);
                          }}
                          disabled={busy}
                        />
                      </td>
                      <td className="py-2 pr-2 text-muted-foreground">{row.notes || '—'}</td>
                      <td className="py-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => removeAssignment(row.id)}
                          disabled={busy}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <form
            onSubmit={saveAssignment}
            className="grid gap-3 rounded-md border border-dashed border-border/70 p-4 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="sm:col-span-2">
              <Label>Add component for this person</Label>
              <select
                className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.component}
                onChange={(ev) => setForm({ ...form, component: ev.target.value })}
                required
              >
                <option value="">Choose…</option>
                {availableToAdd.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name} ({c.kind})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Amount (add / deduct)</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={form.amount}
                onChange={(ev) => setForm({ ...form, amount: ev.target.value })}
                placeholder="e.g. 5000"
              />
            </div>
            <div>
              <Label>Notes</Label>
              <Input
                value={form.notes}
                onChange={(ev) => setForm({ ...form, notes: ev.target.value })}
                placeholder="Optional"
              />
            </div>
            <div className="sm:col-span-2 lg:col-span-4">
              <Button type="submit" size="sm" disabled={busy || !availableToAdd.length}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Add for this employee
              </Button>
              <p className="mt-2 text-xs text-muted-foreground">
                Earnings increase pay; deductions reduce it. Leave amount blank to use the
                component’s template default / %.
              </p>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
