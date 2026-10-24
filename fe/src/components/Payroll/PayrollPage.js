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
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { PageShell, PageHeader } from '../page';
import { cn } from '../../lib/cn';

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
  const [tab, setTab] = useState('runs');
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
      await Promise.all([loadRuns(), loadComponents(), loadSettings(), loadMine()]);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load payroll');
    } finally {
      setLoading(false);
    }
  }, [loadRuns, loadComponents, loadSettings, loadMine]);

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

  const openPdf = async (payslipId, mine = false) => {
    try {
      const res = mine
        ? await payrollAPI.myPayslipPdf(payslipId)
        : await payrollAPI.payslipPdf(payslipId);
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      toast.error('Could not open payslip PDF');
    }
  };

  const tabs = [
    { id: 'runs', label: 'Runs' },
    { id: 'components', label: 'Components' },
    { id: 'settings', label: 'Settings' },
    { id: 'mine', label: 'My payslips' },
  ];

  return (
    <PageShell>
      <PageHeader
        title="Payroll"
        description="Monthly payroll runs, pay components, and payslips"
        icon={Wallet}
        actions={
          <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            Refresh
          </Button>
        }
      />

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

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-12 justify-center">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading payroll…
        </div>
      ) : null}

      {!loading && tab === 'runs' ? (
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

      {!loading && tab === 'components' ? (
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
              {components.map((c) => (
                <tr key={c.id} className="border-b border-border/40">
                  <td className="p-3 font-mono text-xs">{c.code}</td>
                  <td className="p-3">{c.name}</td>
                  <td className="p-3">{c.kind}</td>
                  <td className="p-3">{c.calculation_type}</td>
                  <td className="p-3">{c.is_statutory ? 'Yes' : '—'}</td>
                  <td className="p-3">
                    {c.is_active ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-muted-foreground" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {!loading && tab === 'settings' && settings ? (
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
            <Label htmlFor="letterhead">Letterhead line</Label>
            <Input
              id="letterhead"
              value={settings.letterhead_line || ''}
              onChange={(e) => setSettings({ ...settings, letterhead_line: e.target.value })}
              placeholder="Optional line under store brand on payslips"
            />
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

      {!loading && tab === 'mine' ? (
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
                    No locked payslips linked to your account email yet.
                  </td>
                </tr>
              ) : (
                myPayslips.map((p) => (
                  <tr key={p.id} className="border-b border-border/40">
                    <td className="p-3">{p.period}</td>
                    <td className="p-3">{formatCurrency(p.gross_pay)}</td>
                    <td className="p-3">{formatCurrency(p.net_pay)}</td>
                    <td className="p-3">
                      <Button type="button" size="sm" variant="outline" onClick={() => openPdf(p.id, true)}>
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
      ) : null}
    </PageShell>
  );
}
