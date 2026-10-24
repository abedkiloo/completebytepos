import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Calculator,
  CheckCircle2,
  FileText,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Send,
  Wallet,
  XCircle,
} from 'lucide-react';

import { payrollAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { PageShell, PageHeader } from '../page';
import { cn } from '../../lib/cn';
import StaffPayPanel from './StaffPayPanel';
import RolePackagesPanel from './RolePackagesPanel';

function payrollAccess() {
  const { permissions, user, profile } = getStoredAuth();
  const isSuper =
    Boolean(user?.is_superuser) ||
    profile?.role === 'super_admin' ||
    profile?.is_super_admin ||
    profile?.custom_role?.name === 'Super Admin';
  const canAdmin =
    isSuper ||
    hasPermission(permissions, 'payroll', 'view') ||
    hasPermission(permissions, 'payroll', 'manage');
  const canOwn =
    isSuper || canAdmin || hasPermission(permissions, 'payroll', 'view_own');
  return { canAdmin, canOwn };
}

const STATUS_TONE = {
  draft: 'secondary',
  calculated: 'default',
  pending_approval: 'warning',
  locked: 'success',
  cancelled: 'destructive',
};

function unwrapList(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function currentPeriod() {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

export default function PayrollPage() {
  const { canAdmin, canOwn } = useMemo(() => payrollAccess(), []);
  const [tab, setTab] = useState(canAdmin ? 'runs' : 'mine');
  const [staffFocusId, setStaffFocusId] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [components, setComponents] = useState([]);
  const [settings, setSettings] = useState(null);
  const [myPayslips, setMyPayslips] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [payslips, setPayslips] = useState([]);
  const [summary, setSummary] = useState(null);
  const period = useMemo(() => currentPeriod(), []);
  const [newYear, setNewYear] = useState(period.year);
  const [newMonth, setNewMonth] = useState(period.month);
  const [newComp, setNewComp] = useState({
    name: '',
    code: '',
    kind: 'earning',
    calculation_type: 'fixed',
    default_amount: '',
    default_rate: '',
    is_taxable: true,
  });

  const suggestCode = (name) =>
    String(name || '')
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, '_')
      .replace(/^_|_$/g, '')
      .slice(0, 40);

  const loadRuns = useCallback(async () => {
    const res = await payrollAPI.listRuns({ page_size: 50 });
    setRuns(unwrapList(res.data));
  }, []);

  const loadComponents = useCallback(async () => {
    const res = await payrollAPI.listComponents({ page_size: 100 });
    setComponents(unwrapList(res.data));
  }, []);

  const loadSettings = useCallback(async () => {
    const res = await payrollAPI.getSettings();
    setSettings(res.data);
  }, []);

  const loadMine = useCallback(async () => {
    const res = await payrollAPI.myPayslips();
    setMyPayslips(unwrapList(res.data.results || res.data));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const tasks = [];
      if (canOwn) tasks.push(loadMine());
      if (canAdmin) {
        tasks.push(loadRuns(), loadComponents(), loadSettings());
      }
      await Promise.all(tasks);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load payroll');
    } finally {
      setLoading(false);
    }
  }, [canAdmin, canOwn, loadRuns, loadComponents, loadSettings, loadMine]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openRun = async (run) => {
    setSelectedRun(run);
    try {
      const [slips, sum] = await Promise.all([
        payrollAPI.runPayslips(run.id),
        payrollAPI.runSummary(run.id),
      ]);
      setPayslips(unwrapList(slips.data));
      setSummary(sum.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load run details');
    }
  };

  const act = async (runId, action, label) => {
    setBusyId(`${runId}-${action}`);
    try {
      const fn = {
        calculate: payrollAPI.calculateRun,
        submit: payrollAPI.submitRun,
        approve: payrollAPI.approveRun,
        reject: payrollAPI.rejectRun,
        cancel: payrollAPI.cancelRun,
      }[action];
      const res = await fn(runId);
      toast.success(`${label} succeeded`);
      await loadRuns();
      if (selectedRun?.id === runId) {
        await openRun(res.data);
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || `${label} failed`);
    } finally {
      setBusyId(null);
    }
  };

  const createRun = async () => {
    setBusyId('create');
    try {
      const res = await payrollAPI.createRun({ year: Number(newYear), month: Number(newMonth) });
      toast.success(`Created ${res.data.period}`);
      await loadRuns();
      await openRun(res.data);
      setTab('runs');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not create run');
    } finally {
      setBusyId(null);
    }
  };

  const saveSettings = async () => {
    setBusyId('settings');
    try {
      const res = await payrollAPI.updateSettings({
        currency: settings.currency,
        pay_day: Number(settings.pay_day),
        statutory_enabled: Boolean(settings.statutory_enabled),
        include_appraisal_bonus: Boolean(settings.include_appraisal_bonus),
        letterhead_line: settings.letterhead_line || '',
      });
      setSettings(res.data);
      toast.success('Payroll settings saved');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Save failed');
    } finally {
      setBusyId(null);
    }
  };

  const seedComponents = async () => {
    setBusyId('seed');
    try {
      const res = await payrollAPI.seedComponents();
      const created = res.data?.created ?? 0;
      await loadComponents();
      toast.success(
        created > 0
          ? `Added ${created} starter component${created === 1 ? '' : 's'}`
          : 'Starter library already loaded'
      );
    } catch (err) {
      toast.error(
        err?.response?.data?.detail ||
          'Could not load starters — need payroll.manage permission'
      );
    } finally {
      setBusyId(null);
    }
  };

  const createComponent = async (e) => {
    e?.preventDefault?.();
    const name = (newComp.name || '').trim();
    const code = (newComp.code || suggestCode(name) || '').trim().toUpperCase();
    if (!name || !code) {
      toast.error('Name and code are required');
      return;
    }
    setBusyId('create-comp');
    try {
      const payload = {
        name,
        code,
        kind: newComp.kind || 'earning',
        calculation_type: newComp.calculation_type || 'fixed',
        is_taxable: Boolean(newComp.is_taxable),
        is_statutory: false,
        is_active: true,
        default_amount: newComp.default_amount === '' ? '0' : String(newComp.default_amount),
        default_rate: newComp.default_rate === '' ? '0' : String(newComp.default_rate),
      };
      await payrollAPI.createComponent(payload);
      setNewComp({
        name: '',
        code: '',
        kind: 'earning',
        calculation_type: 'fixed',
        default_amount: '',
        default_rate: '',
        is_taxable: true,
      });
      await loadComponents();
      toast.success(
        `${code} added — set amount under Role packages or Staff pay, then recalculate`
      );
    } catch (err) {
      const data = err?.response?.data;
      const msg =
        data?.code?.[0] ||
        data?.name?.[0] ||
        data?.detail ||
        (typeof data === 'string' ? data : null) ||
        'Could not create component — need payroll.manage';
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  };

  const toggleComponentActive = async (component) => {
    const next = !component.is_active;
    setBusyId(`comp-${component.id}`);
    // Optimistic UI
    setComponents((prev) =>
      prev.map((c) => (c.id === component.id ? { ...c, is_active: next } : c))
    );
    try {
      await payrollAPI.updateComponent(component.id, { is_active: next });
      toast.success(
        next
          ? `${component.code} enabled`
          : `${component.code} disabled — skipped on next calculate`
      );
    } catch (err) {
      setComponents((prev) =>
        prev.map((c) =>
          c.id === component.id ? { ...c, is_active: component.is_active } : c
        )
      );
      toast.error(
        err?.response?.data?.detail ||
          'Could not update — need payroll.manage permission'
      );
    } finally {
      setBusyId(null);
    }
  };

  const openPdf = async (payslipId, mine = false, periodLabel = '') => {
    try {
      const res = mine
        ? await payrollAPI.myPayslipPdf(payslipId)
        : await payrollAPI.payslipPdf(payslipId);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const filename = `payslip_${periodLabel || payslipId}.pdf`.replace(/\s+/g, '_');
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (err) {
      toast.error('Could not download payslip PDF');
    }
  };

  const tabs = [
    ...(canAdmin
      ? [
          { id: 'runs', label: 'Runs' },
          { id: 'packages', label: 'Role packages' },
          { id: 'staff', label: 'Staff pay' },
          { id: 'components', label: 'Components' },
          { id: 'settings', label: 'Settings' },
        ]
      : []),
    ...(canOwn ? [{ id: 'mine', label: 'My payslips' }] : []),
  ];

  if (!canOwn && !canAdmin) {
    return (
      <PageShell>
        <PageHeader
          title="Payslips"
          description="You do not have access to payroll."
          icon={Wallet}
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title={canAdmin ? 'Payroll' : 'My payslips'}
        description={
          canAdmin
            ? 'Monthly payroll runs, pay components, and payslips'
            : 'Download your locked payslips after payroll is approved for the period'
        }
        icon={Wallet}
        actions={
          <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            Refresh
          </Button>
        }
      />

      {tabs.length > 1 ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {tabs.map((t) => (
            <Button
              key={t.id}
              type="button"
              size="sm"
              variant={tab === t.id ? 'default' : 'outline'}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </Button>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-12 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading payroll…
        </div>
      ) : null}

      {!loading && canAdmin && tab === 'runs' ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <section className="space-y-4">
            <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border/60 bg-background/60 p-4">
              <div>
                <Label htmlFor="pay-year">Year</Label>
                <Input
                  id="pay-year"
                  type="number"
                  value={newYear}
                  onChange={(e) => setNewYear(e.target.value)}
                  className="w-28"
                />
              </div>
              <div>
                <Label htmlFor="pay-month">Month</Label>
                <Input
                  id="pay-month"
                  type="number"
                  min={1}
                  max={12}
                  value={newMonth}
                  onChange={(e) => setNewMonth(e.target.value)}
                  className="w-24"
                />
              </div>
              <Button type="button" onClick={createRun} disabled={busyId === 'create'}>
                {busyId === 'create' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                New run
              </Button>
            </div>

            <ul className="divide-y divide-border/60 rounded-lg border border-border/60">
              {runs.length === 0 ? (
                <li className="p-6 text-sm text-muted-foreground">No payroll runs yet.</li>
              ) : (
                runs.map((run) => (
                  <li
                    key={run.id}
                    className={cn(
                      'flex flex-wrap items-center justify-between gap-3 p-4 cursor-pointer hover:bg-muted/40',
                      selectedRun?.id === run.id && 'bg-muted/50'
                    )}
                    onClick={() => openRun(run)}
                  >
                    <div>
                      <div className="font-medium">{run.period}</div>
                      <div className="text-xs text-muted-foreground">
                        {run.employee_count} staff · Net {formatCurrency(run.net_total)}
                      </div>
                    </div>
                    <Badge variant={STATUS_TONE[run.status] || 'secondary'}>{run.status}</Badge>
                  </li>
                ))
              )}
            </ul>
          </section>

          <section className="space-y-4 rounded-lg border border-border/60 p-4 min-h-[320px]">
            {!selectedRun ? (
              <p className="text-sm text-muted-foreground py-8 text-center">Select a run to manage payslips.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">{selectedRun.period}</h2>
                    <p className="text-sm text-muted-foreground">
                      Gross {formatCurrency(selectedRun.gross_total)} · Deductions{' '}
                      {formatCurrency(selectedRun.deduction_total)} · Net{' '}
                      {formatCurrency(selectedRun.net_total)}
                    </p>
                  </div>
                  <Badge variant={STATUS_TONE[selectedRun.status] || 'secondary'}>
                    {selectedRun.status}
                  </Badge>
                </div>

                <div className="flex flex-wrap gap-2">
                  {selectedRun.can_calculate ? (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => act(selectedRun.id, 'calculate', 'Calculate')}
                      disabled={!!busyId}
                    >
                      <Calculator className="h-4 w-4" />
                      Calculate
                    </Button>
                  ) : null}
                  {selectedRun.can_submit ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => act(selectedRun.id, 'submit', 'Submit')}
                      disabled={!!busyId}
                    >
                      <Send className="h-4 w-4" />
                      Submit
                    </Button>
                  ) : null}
                  {selectedRun.can_approve ? (
                    <>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => act(selectedRun.id, 'approve', 'Approve & lock')}
                        disabled={!!busyId}
                      >
                        <Lock className="h-4 w-4" />
                        Approve & lock
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => act(selectedRun.id, 'reject', 'Reject')}
                        disabled={!!busyId}
                      >
                        <XCircle className="h-4 w-4" />
                        Send back
                      </Button>
                    </>
                  ) : null}
                  {selectedRun.can_cancel ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => act(selectedRun.id, 'cancel', 'Cancel')}
                      disabled={!!busyId}
                    >
                      Cancel run
                    </Button>
                  ) : null}
                </div>

                {summary?.by_department?.length ? (
                  <div className="text-xs text-muted-foreground">
                    By department:{' '}
                    {summary.by_department
                      .map((d) => `${d.department} (${d.count})`)
                      .join(' · ')}
                  </div>
                ) : null}

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="py-2 pr-3">Employee</th>
                        <th className="py-2 pr-3">Gross</th>
                        <th className="py-2 pr-3">Net</th>
                        <th className="py-2">PDF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payslips.map((p) => (
                        <tr key={p.id} className="border-b border-border/40">
                          <td className="py-2 pr-3">
                            <div className="font-medium">{p.employee_name_snapshot}</div>
                            <div className="text-xs text-muted-foreground">{p.employee_id_snapshot}</div>
                          </td>
                          <td className="py-2 pr-3">{formatCurrency(p.gross_pay)}</td>
                          <td className="py-2 pr-3">{formatCurrency(p.net_pay)}</td>
                          <td className="py-2">
                            <Button type="button" size="sm" variant="ghost" onClick={() => openPdf(p.id)}>
                              <FileText className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                      {payslips.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="py-6 text-center text-muted-foreground">
                            Calculate this run to generate payslips.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        </div>
      ) : null}

      {!loading && canAdmin && tab === 'packages' ? (
        <RolePackagesPanel
          components={components}
          onEditEmployee={(employeeId) => {
            setStaffFocusId(String(employeeId));
            setTab('staff');
          }}
        />
      ) : null}

      {!loading && canAdmin && tab === 'staff' ? (
        <StaffPayPanel
          components={components}
          initialEmployeeId={staffFocusId}
        />
      ) : null}

      {!loading && canAdmin && tab === 'components' ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground max-w-xl">
              Add your own allowances (e.g. Food) or deductions here. Keep Active on,
              assign amounts under Role packages or Staff pay, then recalculate the run
              so they show on the payslip.
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={seedComponents}
              disabled={busyId === 'seed'}
            >
              {busyId === 'seed' ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Load starter library
            </Button>
          </div>

          <form
            onSubmit={createComponent}
            className="rounded-lg border border-border/60 p-4 space-y-3"
          >
            <div className="text-sm font-medium">Add custom component</div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div className="sm:col-span-2 lg:col-span-1">
                <Label htmlFor="comp_name">Name</Label>
                <Input
                  id="comp_name"
                  value={newComp.name}
                  placeholder="Food allowance"
                  onChange={(e) => {
                    const name = e.target.value;
                    setNewComp((prev) => ({
                      ...prev,
                      name,
                      code:
                        !prev.code || prev.code === suggestCode(prev.name)
                          ? suggestCode(name)
                          : prev.code,
                    }));
                  }}
                />
              </div>
              <div>
                <Label htmlFor="comp_code">Code</Label>
                <Input
                  id="comp_code"
                  value={newComp.code}
                  placeholder="FOOD_ALLOWANCE"
                  className="font-mono text-xs uppercase"
                  onChange={(e) =>
                    setNewComp((prev) => ({
                      ...prev,
                      code: e.target.value.toUpperCase().replace(/\s+/g, '_'),
                    }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="comp_kind">Kind</Label>
                <select
                  id="comp_kind"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={newComp.kind}
                  onChange={(e) =>
                    setNewComp((prev) => ({ ...prev, kind: e.target.value }))
                  }
                >
                  <option value="earning">Earning / allowance</option>
                  <option value="deduction">Deduction</option>
                  <option value="employer">Employer contribution</option>
                </select>
              </div>
              <div>
                <Label htmlFor="comp_calc">Calculation</Label>
                <select
                  id="comp_calc"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={newComp.calculation_type}
                  onChange={(e) =>
                    setNewComp((prev) => ({
                      ...prev,
                      calculation_type: e.target.value,
                    }))
                  }
                >
                  <option value="fixed">Fixed amount</option>
                  <option value="percent_basic">% of basic</option>
                  <option value="percent_gross">% of gross</option>
                </select>
              </div>
              {newComp.calculation_type === 'fixed' ? (
                <div>
                  <Label htmlFor="comp_amount">Default amount</Label>
                  <Input
                    id="comp_amount"
                    type="number"
                    min="0"
                    step="0.01"
                    value={newComp.default_amount}
                    placeholder="0"
                    onChange={(e) =>
                      setNewComp((prev) => ({
                        ...prev,
                        default_amount: e.target.value,
                      }))
                    }
                  />
                </div>
              ) : (
                <div>
                  <Label htmlFor="comp_rate">Rate (e.g. 0.05 = 5%)</Label>
                  <Input
                    id="comp_rate"
                    type="number"
                    min="0"
                    step="0.0001"
                    value={newComp.default_rate}
                    placeholder="0.05"
                    onChange={(e) =>
                      setNewComp((prev) => ({
                        ...prev,
                        default_rate: e.target.value,
                      }))
                    }
                  />
                </div>
              )}
              <div className="flex items-end">
                <label className="inline-flex items-center gap-2 text-sm cursor-pointer select-none pb-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={Boolean(newComp.is_taxable)}
                    onChange={(e) =>
                      setNewComp((prev) => ({
                        ...prev,
                        is_taxable: e.target.checked,
                      }))
                    }
                  />
                  Taxable
                </label>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" size="sm" disabled={busyId === 'create-comp'}>
                {busyId === 'create-comp' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Add to library
              </Button>
              <span className="text-xs text-muted-foreground">
                Then set who gets it under Role packages or Staff pay.
              </span>
            </div>
          </form>

          {components.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/80 p-10 text-center text-sm text-muted-foreground">
              No components yet. Add Food allowance above, or load the starter library.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border/60">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/30 text-left">
                    <th className="p-3">Code</th>
                    <th className="p-3">Name</th>
                    <th className="p-3">Kind</th>
                    <th className="p-3">Calc</th>
                    <th className="p-3">Statutory</th>
                    <th className="p-3">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {components.map((c) => {
                    const toggling = busyId === `comp-${c.id}`;
                    return (
                      <tr
                        key={c.id}
                        className={cn(
                          'border-b border-border/40',
                          !c.is_active && 'opacity-60'
                        )}
                      >
                        <td className="p-3 font-mono text-xs">{c.code}</td>
                        <td className="p-3">{c.name}</td>
                        <td className="p-3">{c.kind}</td>
                        <td className="p-3">{c.calculation_type}</td>
                        <td className="p-3">{c.is_statutory ? 'Yes' : '—'}</td>
                        <td className="p-3">
                          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-input"
                              checked={Boolean(c.is_active)}
                              disabled={toggling}
                              onChange={() => toggleComponentActive(c)}
                              aria-label={`${c.is_active ? 'Disable' : 'Enable'} ${c.code}`}
                            />
                            {toggling ? (
                              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            ) : c.is_active ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                            ) : (
                              <XCircle className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span className="text-xs text-muted-foreground">
                              {c.is_active ? 'On' : 'Off'}
                            </span>
                          </label>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {!loading && canAdmin && tab === 'settings' && settings ? (
        <div className="max-w-lg space-y-4 rounded-lg border border-border/60 p-4">
          <div>
            <Label htmlFor="currency">Currency</Label>
            <Input
              id="currency"
              value={settings.currency || ''}
              onChange={(e) => setSettings({ ...settings, currency: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="pay_day">Pay day (1–28)</Label>
            <Input
              id="pay_day"
              type="number"
              min={1}
              max={28}
              value={settings.pay_day ?? 28}
              onChange={(e) => setSettings({ ...settings, pay_day: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="letterhead">Payslip letterhead line</Label>
            <Input
              id="letterhead"
              value={settings.letterhead_line || ''}
              onChange={(e) => setSettings({ ...settings, letterhead_line: e.target.value })}
              placeholder="Optional line under store brand on payslips"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Payslip PDFs are generated on download (not filed away). They use this
              letterhead plus the store logo/name/header from System Settings. Employees
              only see locked payslips after a run is approved.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(settings.include_appraisal_bonus)}
              onChange={(e) =>
                setSettings({ ...settings, include_appraisal_bonus: e.target.checked })
              }
            />
            Include target-delivery bonus when calculating
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(settings.statutory_enabled)}
              onChange={(e) =>
                setSettings({ ...settings, statutory_enabled: e.target.checked })
              }
            />
            Enable statutory deductions (PAYE / NSSF / SHIF) — off by default
          </label>
          <Button type="button" onClick={saveSettings} disabled={busyId === 'settings'}>
            {busyId === 'settings' ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save settings
          </Button>
        </div>
      ) : null}

      {!loading && canOwn && tab === 'mine' ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground max-w-2xl">
            After payroll is approved and locked for a period, your payslip appears here.
            Download builds a fresh PDF on request (not stored) with the company logo and
            letterhead from store / payroll settings — same idea as receipts.
          </p>
          <div className="overflow-x-auto rounded-lg border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left">
                  <th className="p-3">Period</th>
                  <th className="p-3">Gross</th>
                  <th className="p-3">Net</th>
                  <th className="p-3">PDF</th>
                </tr>
              </thead>
              <tbody>
                {myPayslips.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      No locked payslips yet. Link your user to an employee record, then wait
                      until payroll for the period is approved.
                    </td>
                  </tr>
                ) : (
                  myPayslips.map((p) => (
                    <tr key={p.id} className="border-b border-border/40">
                      <td className="p-3">{p.period}</td>
                      <td className="p-3">{formatCurrency(p.gross_pay)}</td>
                      <td className="p-3">{formatCurrency(p.net_pay)}</td>
                      <td className="p-3">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => openPdf(p.id, true, p.period)}
                        >
                          <FileText className="h-4 w-4" />
                          Download
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </PageShell>
  );
}
