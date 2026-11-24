import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';

import { employeesAPI, payrollAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import {
  mergeInheritedPayLines,
  personalPackageOverridePayload,
} from '../../utils/staffPayLines';
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
 * Per-employee overrides on top of the role template (general package).
 * Template applies automatically; lines here win for this person only
 * (including sales commission rate).
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

  const packageComponentIds = useMemo(
    () =>
      new Set(
        (rolePackage?.lines || [])
          .filter((line) => line?.is_active !== false)
          .map((line) => Number(line.component)),
      ),
    [rolePackage],
  );

  const assignedIds = useMemo(
    () => new Set(assignments.map((a) => a.component)),
    [assignments]
  );

  const availableToAdd = useMemo(
    () =>
      assignableComponents.filter(
        (c) => !assignedIds.has(c.id) && !packageComponentIds.has(Number(c.id)),
      ),
    [assignableComponents, assignedIds, packageComponentIds],
  );

  const extraAssignments = useMemo(
    () =>
      assignments.filter((row) => !packageComponentIds.has(Number(row.component))),
    [assignments, packageComponentIds],
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

  const updateRate = async (row, rate) => {
    setBusy(true);
    try {
      await payrollAPI.updateAssignment(row.id, {
        rate: rate === '' ? null : rate,
      });
      await loadAssignments(employeeId);
      await loadPayPreview(employeeId);
      toast.success('Rate updated');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Update failed');
    } finally {
      setBusy(false);
    }
  };

  const formatRate = (rate) => {
    if (rate == null || rate === '') return null;
    const n = Number(rate);
    if (Number.isNaN(n)) return String(rate);
    return `${(n * 100).toFixed(2)}%`;
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

  const refreshPerson = async () => {
    await loadAssignments(employeeId);
    await loadPayPreview(employeeId);
  };

  const upsertPersonalOverride = async ({
    componentId,
    amount,
    rate = null,
    notes = '',
    existingId = null,
  }) => {
    const payload = personalPackageOverridePayload({
      employeeId,
      componentId,
      amount,
      rate,
      notes,
    });
    if (existingId) {
      await payrollAPI.updateAssignment(existingId, {
        amount: payload.amount,
        rate: payload.rate,
        notes: payload.notes,
        is_active: true,
      });
    } else {
      await payrollAPI.createAssignment(payload);
    }
  };

  const editInheritedAmount = async (row, nextAmount) => {
    const prev =
      row.personalAmount != null
        ? row.personalAmount
        : row.packageAmount != null
          ? row.packageAmount
          : '';
    if (String(nextAmount) === String(prev)) return;
    setBusy(true);
    try {
      await upsertPersonalOverride({
        componentId: row.componentId,
        amount: nextAmount === '' ? '0' : nextAmount,
        rate: row.personalRate != null ? row.personalRate : row.packageRate,
        notes: row.override?.notes || 'Personal package amount',
        existingId: row.override?.id || null,
      });
      await refreshPerson();
      toast.success('Amount updated for this employee only');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not update amount');
    } finally {
      setBusy(false);
    }
  };

  const removeInheritedForPerson = async (row) => {
    setBusy(true);
    try {
      await upsertPersonalOverride({
        componentId: row.componentId,
        amount: '0',
        rate: null,
        notes: 'Removed from role package for this employee',
        existingId: row.override?.id || null,
      });
      await refreshPerson();
      toast.success('Removed for this employee — role package unchanged');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not remove amount');
    } finally {
      setBusy(false);
    }
  };

  const restoreInheritedForPerson = async (row) => {
    if (!row.override?.id) return;
    setBusy(true);
    try {
      await payrollAPI.deleteAssignment(row.override.id);
      await refreshPerson();
      toast.success('Restored role package amount for this employee');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not restore');
    } finally {
      setBusy(false);
    }
  };

  const inheritedRows = useMemo(
    () => mergeInheritedPayLines(rolePackage, assignments),
    [rolePackage, assignments],
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
        Role package amounts apply automatically. For one person you can edit an
        amount, remove a package line, or add an extra component — the role template
        itself stays the same for everyone else.
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
            <div className="rounded-md border border-dashed bg-muted/20 p-3 space-y-3">
              <div className="text-sm font-medium">
                Package lines for {rolePackage.role_name || rolePackage.name}
                <span className="ml-2 font-normal text-muted-foreground">
                  — edit or remove for this person only
                </span>
              </div>
              {inheritedRows.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Role template exists but has no active lines yet. Set default basic
                  and add allowances under Role templates.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-2 pr-2">Component</th>
                        <th className="py-2 pr-2">Package</th>
                        <th className="py-2 pr-2">This person (KES)</th>
                        <th className="py-2 pr-2">Status</th>
                        <th className="py-2"> </th>
                      </tr>
                    </thead>
                    <tbody>
                      {inheritedRows.map((row) => (
                        <tr key={row.packageLineId} className="border-b border-border/40">
                          <td className="py-2 pr-2">
                            <div className="font-medium">{row.componentName}</div>
                            <div className="font-mono text-xs text-muted-foreground">
                              {row.componentCode}
                            </div>
                          </td>
                          <td className="py-2 pr-2 text-muted-foreground">
                            {row.packageAmount != null
                              ? formatCurrency(row.packageAmount)
                              : formatRate(row.packageRate) || '—'}
                          </td>
                          <td className="py-2 pr-2">
                            <Input
                              className="w-32"
                              type="number"
                              step="0.01"
                              min="0"
                              defaultValue={
                                row.removed
                                  ? '0'
                                  : row.personalAmount != null
                                    ? row.personalAmount
                                    : row.packageAmount ?? ''
                              }
                              key={`${row.packageLineId}-${row.status}-${row.effectiveAmount}`}
                              placeholder="Amount"
                              onBlur={(ev) => editInheritedAmount(row, ev.target.value)}
                              disabled={busy}
                              aria-label={`Amount for ${row.componentName}`}
                            />
                          </td>
                          <td className="py-2 pr-2">
                            <Badge
                              variant={
                                row.status === 'removed'
                                  ? 'destructive'
                                  : row.status === 'edited'
                                    ? 'secondary'
                                    : 'outline'
                              }
                            >
                              {row.status === 'removed'
                                ? 'Removed'
                                : row.status === 'edited'
                                  ? 'Personal amount'
                                  : 'Inherited'}
                            </Badge>
                          </td>
                          <td className="py-2">
                            <div className="flex flex-wrap gap-1 justify-end">
                              {row.status === 'inherited' ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => removeInheritedForPerson(row)}
                                  disabled={busy}
                                  aria-label={`Remove ${row.componentName} for this employee`}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  Remove
                                </Button>
                              ) : (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => restoreInheritedForPerson(row)}
                                  disabled={busy}
                                >
                                  Restore package
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Changing an amount or pressing Remove only affects this employee.
                Current gross above already reflects those edits.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No role package found for this person. Under Employees, set Position /
              job role to <strong>Sales Personnel</strong> (or their role), and create
              that role template — or add personal lines here (e.g. commission rate).
            </p>
          )}

          <div className="text-sm font-medium">Extra personal lines (not on the package)</div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-2">Component</th>
                  <th className="py-2 pr-2">Kind</th>
                  <th className="py-2 pr-2">Amount (KES)</th>
                  <th className="py-2 pr-2">Rate</th>
                  <th className="py-2 pr-2">Notes</th>
                  <th className="py-2"> </th>
                </tr>
              </thead>
              <tbody>
                {extraAssignments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-muted-foreground">
                      No extra lines — use the package table above to change inherited
                      amounts, or add a component here.
                    </td>
                  </tr>
                ) : (
                  extraAssignments.map((row) => {
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
                      <td className="py-2 pr-2">
                        <Input
                          className="w-28"
                          type="number"
                          step="0.0001"
                          min="0"
                          defaultValue={row.rate ?? ''}
                          placeholder="0.03"
                          onBlur={(ev) => {
                            const next = ev.target.value;
                            const prev = row.rate == null ? '' : String(row.rate);
                            if (next !== prev) updateRate(row, next);
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
            className="grid gap-3 rounded-md border border-dashed border-border/70 p-4 sm:grid-cols-2 lg:grid-cols-5"
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
              <Label>Rate (e.g. 0.03 = 3%)</Label>
              <Input
                type="number"
                step="0.0001"
                min="0"
                value={form.rate}
                onChange={(ev) => setForm({ ...form, rate: ev.target.value })}
                placeholder="0.03 for commission"
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
            <div className="sm:col-span-2 lg:col-span-5">
              <Button type="submit" size="sm" disabled={busy || !availableToAdd.length}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Add for this employee
              </Button>
              <p className="mt-2 text-xs text-muted-foreground">
                Earnings increase pay; deductions reduce it. For sales commission, set
                Rate (leave Amount blank). Rate is a fraction — 0.05 means 5%.
              </p>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
