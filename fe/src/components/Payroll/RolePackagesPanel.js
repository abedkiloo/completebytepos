import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, Trash2 } from 'lucide-react';

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

/**
 * Default pay package per job role. Staff pay overrides one person later.
 */
export default function RolePackagesPanel({ components = [] }) {
  const [roles, setRoles] = useState([]);
  const [packages, setPackages] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [pkg, setPkg] = useState(null);
  const [loading, setLoading] = useState(true);
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
  }, [refresh]);

  const packageForRole = useCallback(
    (roleId) => packages.find((p) => String(p.role) === String(roleId)) || null,
    [packages]
  );

  const selectRole = async (roleId) => {
    setSelectedRoleId(roleId);
    const existing = packageForRole(roleId);
    if (existing) {
      try {
        const res = await payrollAPI.getPackage(existing.id);
        setPkg(res.data);
        setDefaultBasic(
          res.data.default_basic != null ? String(res.data.default_basic) : ''
        );
      } catch {
        setPkg(existing);
        setDefaultBasic(
          existing.default_basic != null ? String(existing.default_basic) : ''
        );
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
      toast.success('Role package created');
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
      toast.success('Package saved');
      await refresh();
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
      toast.success('Line added to role package');
      await refresh();
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
      toast.success('Removed from package');
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
        Set one pay package per job role (e.g. Sales, Manager). Everyone on that role
        gets these defaults when you calculate payroll. Change one person later under
        Staff pay without editing the whole role.
      </p>

      <div className="max-w-md space-y-2">
        <Label htmlFor="pkg-role">Job role</Label>
        <select
          id="pkg-role"
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
          value={selectedRoleId}
          onChange={(e) => selectRole(e.target.value)}
        >
          <option value="">Select role…</option>
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
            {pkg ? (
              <Badge variant="secondary">{pkg.display_name || pkg.name}</Badge>
            ) : null}
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
              No lines yet — add allowances or deductions for this role below.
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
                Add line
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
