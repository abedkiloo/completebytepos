import React, { useMemo, useState } from 'react';
import { Plus, Trash2, Save } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { kes } from '../../utils/appraisalStars';
import { filterRoleDailyTargets, isAppraisalAdminRole } from '../../utils/appraisalRoles';
import { cn } from '../../lib/cn';

const SECTIONS = [
  { key: 'role', label: 'Role & pay' },
  { key: 'stars', label: 'Daily stars' },
  { key: 'bonus', label: 'Monthly bonus' },
  { key: 'tips', label: 'Daily tips' },
  { key: 'options', label: 'Visibility' },
  { key: 'publish', label: 'Publish' },
];

const LOCKED_ROLES = ['Manager', 'Sales Personnel', 'Field Sales'];

function num(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function BandTable({ title, hint, rows, columns, onChange, onAdd, onRemove }) {
  return (
    <div className="space-y-2" data-testid="appraisal-band-table">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{title}</p>
          {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        <Button type="button" size="sm" variant="outline" onClick={onAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add
        </Button>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full min-w-[28rem] text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              {columns.map((col) => (
                <th key={col.key} className="px-2 py-2 font-medium">{col.label}</th>
              ))}
              <th className="w-10 px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.min}-${index}`} className="border-b border-border/60 last:border-0">
                {columns.map((col) => (
                  <td key={col.key} className="px-2 py-1.5">
                    <Input
                      type={col.type || 'number'}
                      step={col.step}
                      value={row[col.key] ?? ''}
                      onChange={(e) => onChange(index, col.key, e.target.value)}
                      className="h-8"
                    />
                  </td>
                ))}
                <td className="px-1 py-1.5">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => onRemove(index)}
                    aria-label="Remove band"
                    disabled={rows.length <= 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function roleTargetsFromPolicy(policy) {
  const incoming = policy?.role_daily_targets && typeof policy.role_daily_targets === 'object'
    ? policy.role_daily_targets
    : {};
  return filterRoleDailyTargets({
    Manager: num(incoming.Manager, num(policy?.manager_daily_target, 35000)),
    'Sales Personnel': num(incoming['Sales Personnel'], num(policy?.daily_target, 20000)),
    'Field Sales': num(incoming['Field Sales'], num(policy?.daily_target, 20000)),
    ...Object.fromEntries(
      Object.entries(incoming).map(([role, target]) => [role, num(target, 0)]),
    ),
  });
}

function frameworkFromPolicy(policy, role) {
  const incoming = policy?.role_frameworks?.[role] || {};
  return {
    basic_pay: num(incoming.basic_pay, num(policy?.basic_pay, 15000)),
    daily_target: num(incoming.daily_target, num(policy?.role_daily_targets?.[role], policy?.daily_target)),
    year_end_increment: num(incoming.year_end_increment, num(policy?.year_end_increment, 3000)),
    working_days: num(incoming.working_days, num(policy?.working_days, 26)),
    four_star_month_min_avg: num(incoming.four_star_month_min_avg, num(policy?.four_star_month_min_avg, 4)),
    four_star_months_required: num(incoming.four_star_months_required, num(policy?.four_star_months_required, 8)),
    annual_avg_required: num(incoming.annual_avg_required, num(policy?.annual_avg_required, 4)),
    daily_star_bands: incoming.daily_star_bands || policy?.daily_star_bands || [],
    monthly_bonus_bands: incoming.monthly_bonus_bands || policy?.monthly_bonus_bands || [],
  };
}

/** Match backend apply_daily_target: always scale band mins so 4★ = role daily target. */
function rolePreview(form, role) {
  const fw = form.role_frameworks?.[role] || {};
  const target = num(fw.daily_target, num(form.role_daily_targets?.[role], form.daily_target));
  const bands = Array.isArray(fw.daily_star_bands) && fw.daily_star_bands.length
    ? fw.daily_star_bands
    : (form.daily_star_bands || []);
  const bonusBands = Array.isArray(fw.monthly_bonus_bands) && fw.monthly_bonus_bands.length
    ? fw.monthly_bonus_bands
    : (form.monthly_bonus_bands || []);
  const four = bands.find((band) => Math.abs(Number(band.stars) - 4) < 0.01);
  const five = bands.find((band) => Math.abs(Number(band.stars) - 5) < 0.01);
  const bonusFour = bonusBands.find((band) => Math.abs(Number(band.stars) - 4) < 0.01);
  const baseline = num(four?.min, form.daily_target);
  const ratio = baseline > 0 && target > 0 ? target / baseline : 1;
  return {
    role,
    daily_target: target,
    four_star_target: Math.round(num(four?.min, target) * ratio),
    five_star_target: five ? Math.round(num(five?.min, 0) * ratio) : null,
    four_star_bonus_min: bonusFour ? Math.round(num(bonusFour?.min, 0) * ratio) : null,
    year_end_increment: num(fw.year_end_increment, form.year_end_increment),
    four_star_month_min_avg: num(fw.four_star_month_min_avg, form.four_star_month_min_avg),
    four_star_months_required: num(fw.four_star_months_required, form.four_star_months_required),
    annual_avg_required: num(fw.annual_avg_required, form.annual_avg_required),
    basic_pay: num(fw.basic_pay, form.basic_pay),
  };
}

export default function AppraisalTemplateForm({ policy, saving, onSave }) {
  const [form, setForm] = useState(() => ({
    ...policy,
    role_daily_targets: roleTargetsFromPolicy(policy),
    role_frameworks: policy?.role_frameworks || {},
    bonus_min_stars: num(policy?.bonus_min_stars, 4),
    bonus_cap: num(policy?.bonus_cap, 10000),
    staff_facing: policy?.staff_facing !== false,
    change_reason: '',
    effective_from: '',
  }));
  const [section, setSection] = useState('role');
  const [newRole, setNewRole] = useState('');
  const [newRoleTarget, setNewRoleTarget] = useState('');
  const [selectedRole, setSelectedRole] = useState(
    () => (policy?.role_daily_targets?.['Sales Personnel'] != null ? 'Sales Personnel' : Object.keys(roleTargetsFromPolicy(policy))[0] || ''),
  );
  const [selectedTipIndex, setSelectedTipIndex] = useState(0);

  const dailyColumns = useMemo(
    () => [
      { key: 'min', label: 'From (KES)', step: '1' },
      { key: 'stars', label: 'Stars', step: '0.5' },
      { key: 'label', label: 'Label', type: 'text' },
    ],
    [],
  );
  const bonusColumns = useMemo(
    () => [
      { key: 'min', label: 'From (KES)', step: '1' },
      { key: 'stars', label: 'Rating', step: '0.5' },
      { key: 'bonus', label: 'Bonus (KES)', step: '1' },
      { key: 'label', label: 'Label', type: 'text' },
    ],
    [],
  );

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const emptyTipPack = () => ({
    id: `pack-${Date.now()}`,
    title: '',
    why: '',
    tips: ['', '', ''],
  });

  const patchTipPack = (index, key, value) => {
    setForm((prev) => {
      const next = [...(prev.daily_tip_packs || [])];
      next[index] = { ...next[index], [key]: value };
      return { ...prev, daily_tip_packs: next };
    });
  };

  const patchTipLine = (packIndex, tipIndex, value) => {
    setForm((prev) => {
      const next = [...(prev.daily_tip_packs || [])];
      const tips = [...(next[packIndex]?.tips || ['', '', ''])];
      while (tips.length < 3) tips.push('');
      tips[tipIndex] = value;
      next[packIndex] = { ...next[packIndex], tips };
      return { ...prev, daily_tip_packs: next };
    });
  };

  const roleTargets = form.role_daily_targets || {};
  const roleNames = Object.keys(roleTargets).sort((a, b) => a.localeCompare(b));
  const preview = selectedRole ? rolePreview(form, selectedRole) : null;
  const selectedFramework = selectedRole
    ? { ...frameworkFromPolicy(form, selectedRole), ...(form.role_frameworks?.[selectedRole] || {}) }
    : null;
  const tipPacks = form.daily_tip_packs || [];
  const activeTip = tipPacks[selectedTipIndex] || null;

  const patchFramework = (role, key, value) => {
    if (!role) return;
    setForm((prev) => {
      const current = { ...frameworkFromPolicy(prev, role), ...(prev.role_frameworks?.[role] || {}) };
      const nextFramework = { ...current, [key]: value };
      return {
        ...prev,
        role_frameworks: { ...(prev.role_frameworks || {}), [role]: nextFramework },
        role_daily_targets: key === 'daily_target'
          ? { ...(prev.role_daily_targets || {}), [role]: value }
          : prev.role_daily_targets,
      };
    });
  };

  const patchFrameworkBand = (role, listKey, index, key, value) => {
    setForm((prev) => {
      const current = { ...frameworkFromPolicy(prev, role), ...(prev.role_frameworks?.[role] || {}) };
      const rows = [...(current[listKey] || [])];
      rows[index] = { ...rows[index], [key]: key === 'label' ? value : num(value, rows[index][key]) };
      return {
        ...prev,
        role_frameworks: { ...(prev.role_frameworks || {}), [role]: { ...current, [listKey]: rows } },
      };
    });
  };

  const setRoleTarget = (role, value) => {
    setForm((prev) => {
      const current = { ...frameworkFromPolicy(prev, role), ...(prev.role_frameworks?.[role] || {}) };
      return {
        ...prev,
        role_daily_targets: {
          ...(prev.role_daily_targets || {}),
          [role]: value,
        },
        role_frameworks: {
          ...(prev.role_frameworks || {}),
          [role]: { ...current, daily_target: value },
        },
      };
    });
  };

  const addRoleTarget = () => {
    const role = newRole.trim();
    if (!role || isAppraisalAdminRole(role)) return;
    setRoleTarget(role, num(newRoleTarget, num(form.daily_target, 20000)));
    setSelectedRole(role);
    setNewRole('');
    setNewRoleTarget('');
  };

  const removeRoleTarget = (role) => {
    if (LOCKED_ROLES.includes(role)) return;
    setForm((prev) => {
      const next = { ...(prev.role_daily_targets || {}) };
      const frameworks = { ...(prev.role_frameworks || {}) };
      delete next[role];
      delete frameworks[role];
      return { ...prev, role_daily_targets: next, role_frameworks: frameworks };
    });
    if (selectedRole === role) {
      setSelectedRole('Sales Personnel');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const targets = filterRoleDailyTargets(
      Object.fromEntries(
        Object.entries(form.role_daily_targets || {}).map(([role, target]) => [role, num(target)]),
      ),
    );
    onSave({
      ...form,
      basic_pay: num(form.basic_pay),
      role_daily_targets: targets,
      daily_target: num(targets['Sales Personnel'], num(form.daily_target)),
      manager_daily_target: num(targets.Manager, num(form.manager_daily_target, 35000)),
      year_end_increment: num(form.year_end_increment),
      working_days: num(form.working_days, 26),
      four_star_month_min_avg: num(form.four_star_month_min_avg, 4),
      four_star_months_required: num(form.four_star_months_required, 8),
      annual_avg_required: num(form.annual_avg_required, 4),
      bonus_min_stars: num(form.bonus_min_stars, 4),
      bonus_cap: num(form.bonus_cap, 10000),
      show_year_end_increment: Boolean(form.show_year_end_increment),
      staff_facing: form.staff_facing !== false,
      change_reason: String(form.change_reason || '').trim(),
      effective_from: String(form.effective_from || '').trim(),
      role_frameworks: form.role_frameworks || {},
      daily_tip_packs: (form.daily_tip_packs || []).map((pack) => ({
        ...pack,
        title: String(pack.title || '').trim(),
        why: String(pack.why || '').trim(),
        tips: (pack.tips || []).map((tip) => String(tip).trim()).filter(Boolean),
      })),
    });
  };

  const rolePicker = (
    <div className="mb-3">
      <Label htmlFor="selected_role">Editing role</Label>
      <select
        id="selected_role"
        className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm"
        value={selectedRole}
        onChange={(e) => setSelectedRole(e.target.value)}
      >
        {roleNames.map((role) => (
          <option key={role} value={role}>{role}</option>
        ))}
      </select>
    </div>
  );

  return (
    <form className="space-y-4" onSubmit={handleSubmit} data-testid="appraisal-rules-form">
      <div className="grid gap-4 lg:grid-cols-[200px_1fr]">
        <nav className="space-y-1 rounded-lg border bg-card p-2" aria-label="Performance rules sections">
          {SECTIONS.map((row) => (
            <button
              key={row.key}
              type="button"
              onClick={() => setSection(row.key)}
              className={cn(
                'flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-sm transition-colors',
                section === row.key
                  ? 'bg-primary/10 font-medium text-foreground'
                  : 'hover:bg-muted/60',
              )}
            >
              {row.label}
            </button>
          ))}
        </nav>

        <section className="min-w-0 rounded-lg border bg-card p-4 shadow-sm">
          {section === 'role' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Role &amp; pay</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Pick a role, set its daily target and pay. Admin roles are not scored.
                </p>
              </div>
              {rolePicker}
              {selectedFramework ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="fw_basic">Basic salary</Label>
                    <Input id="fw_basic" type="number" value={selectedFramework.basic_pay ?? ''} onChange={(e) => patchFramework(selectedRole, 'basic_pay', e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="fw_target">Daily target</Label>
                    <Input id="fw_target" type="number" value={selectedFramework.daily_target ?? ''} onChange={(e) => patchFramework(selectedRole, 'daily_target', e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="fw_days">Working days / month</Label>
                    <Input id="fw_days" type="number" value={selectedFramework.working_days ?? ''} onChange={(e) => patchFramework(selectedRole, 'working_days', e.target.value)} />
                  </div>
                  {form.show_year_end_increment ? (
                    <div>
                      <Label htmlFor="fw_increment">Annual increment</Label>
                      <Input id="fw_increment" type="number" value={selectedFramework.year_end_increment ?? ''} onChange={(e) => patchFramework(selectedRole, 'year_end_increment', e.target.value)} />
                    </div>
                  ) : null}
                </div>
              ) : null}
              {preview ? (
                <div className="grid gap-2 rounded-md border bg-muted/20 p-3 text-sm sm:grid-cols-2" data-testid="appraisal-rules-preview">
                  <p>Daily target <span className="font-semibold">{kes(preview.daily_target)}</span></p>
                  <p>4★ target <span className="font-semibold">{kes(preview.four_star_target)}</span></p>
                  <p>5★ target <span className="font-semibold">{preview.five_star_target ? `${kes(preview.five_star_target)}+` : '—'}</span></p>
                  <p>4★ bonus from <span className="font-semibold">{preview.four_star_bonus_min != null ? kes(preview.four_star_bonus_min) : '—'}</span></p>
                  <p>Basic <span className="font-semibold">{kes(preview.basic_pay)}</span></p>
                </div>
              ) : null}
              <div className="space-y-2 border-t pt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">All role targets</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {roleNames.map((role) => (
                    <div key={role}>
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <Label htmlFor={`role_target_${role}`}>{role}</Label>
                        {!LOCKED_ROLES.includes(role) ? (
                          <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${role}`} onClick={() => removeRoleTarget(role)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        ) : null}
                      </div>
                      <Input
                        id={`role_target_${role}`}
                        type="number"
                        value={roleTargets[role] ?? ''}
                        onChange={(e) => setRoleTarget(role, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
                <div className="grid gap-2 sm:grid-cols-[1fr_7rem_auto]">
                  <Input placeholder="Add another role…" value={newRole} onChange={(e) => setNewRole(e.target.value)} aria-label="New role name" />
                  <Input type="number" placeholder="KES" value={newRoleTarget} onChange={(e) => setNewRoleTarget(e.target.value)} aria-label="New role daily target" />
                  <Button type="button" variant="outline" onClick={addRoleTarget}>
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    Add
                  </Button>
                </div>
              </div>
            </div>
          ) : null}

          {section === 'stars' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Daily stars</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Sales thresholds that unlock each star for the selected role.
                </p>
              </div>
              {rolePicker}
              <BandTable
                title={`Star bands · ${selectedRole || 'role'}`}
                hint="4★ is target met. Edit per role."
                rows={selectedFramework?.daily_star_bands || []}
                columns={dailyColumns}
                onChange={(i, k, v) => patchFrameworkBand(selectedRole, 'daily_star_bands', i, k, v)}
                onAdd={() => patchFramework(selectedRole, 'daily_star_bands', [...(selectedFramework?.daily_star_bands || []), { min: 0, stars: 1, label: '' }])}
                onRemove={(i) => patchFramework(
                  selectedRole,
                  'daily_star_bands',
                  (selectedFramework?.daily_star_bands || []).filter((_, idx) => idx !== i),
                )}
              />
            </div>
          ) : null}

          {section === 'bonus' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Monthly bonus</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Cash starts at {num(form.bonus_min_stars, 4)}★ with a KES {num(form.bonus_cap, 10000).toLocaleString('en-KE')}{' '}
                  cap. Bands below that keep star labels but must pay 0. Each role has its own ladder.
                </p>
              </div>
              {rolePicker}
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="bonus_min_stars">Bonus starts at (★)</Label>
                  <Input
                    id="bonus_min_stars"
                    type="number"
                    step="0.5"
                    value={form.bonus_min_stars ?? 4}
                    onChange={(e) => setField('bonus_min_stars', e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="bonus_cap">Bonus cap (KES)</Label>
                  <Input
                    id="bonus_cap"
                    type="number"
                    value={form.bonus_cap ?? 10000}
                    onChange={(e) => setField('bonus_cap', e.target.value)}
                  />
                </div>
              </div>
              <BandTable
                title={`Bonus ladder · ${selectedRole || 'role'}`}
                hint="Example: 4★ → 2,000 · 4.5★ → 6,000 · 5★ → 10,000"
                rows={selectedFramework?.monthly_bonus_bands || []}
                columns={bonusColumns}
                onChange={(i, k, v) => patchFrameworkBand(selectedRole, 'monthly_bonus_bands', i, k, v)}
                onAdd={() => patchFramework(selectedRole, 'monthly_bonus_bands', [...(selectedFramework?.monthly_bonus_bands || []), { min: 0, stars: 4, bonus: 2000, label: 'BASE' }])}
                onRemove={(i) => patchFramework(
                  selectedRole,
                  'monthly_bonus_bands',
                  (selectedFramework?.monthly_bonus_bands || []).filter((_, idx) => idx !== i),
                )}
              />
            </div>
          ) : null}

          {section === 'tips' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Daily tips</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  One pack rotates each day. Staff see a single tip first — keep packs short (3 lines).
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-[180px_1fr]">
                <div className="space-y-1 rounded-md border p-2">
                  {tipPacks.map((pack, index) => (
                    <button
                      key={pack.id || index}
                      type="button"
                      onClick={() => setSelectedTipIndex(index)}
                      className={cn(
                        'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm',
                        selectedTipIndex === index ? 'bg-primary/10 font-medium' : 'hover:bg-muted/60',
                      )}
                    >
                      <span className="truncate">{pack.title || `Pack ${index + 1}`}</span>
                    </button>
                  ))}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-2 w-full"
                    onClick={() => {
                      setField('daily_tip_packs', [...tipPacks, emptyTipPack()]);
                      setSelectedTipIndex(tipPacks.length);
                    }}
                  >
                    <Plus className="mr-1 h-3.5 w-3.5" />
                    Add pack
                  </Button>
                </div>
                {activeTip ? (
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="grid flex-1 gap-2 sm:grid-cols-2">
                        <div>
                          <Label htmlFor="tip_title">Title</Label>
                          <Input
                            id="tip_title"
                            value={activeTip.title || ''}
                            onChange={(e) => patchTipPack(selectedTipIndex, 'title', e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="tip_why">Why (optional)</Label>
                          <Input
                            id="tip_why"
                            value={activeTip.why || ''}
                            onChange={(e) => patchTipPack(selectedTipIndex, 'why', e.target.value)}
                          />
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label="Remove tip pack"
                        disabled={tipPacks.length <= 1}
                        onClick={() => {
                          const next = tipPacks.filter((_, idx) => idx !== selectedTipIndex);
                          setField('daily_tip_packs', next);
                          setSelectedTipIndex(Math.max(0, selectedTipIndex - 1));
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    {[0, 1, 2].map((tipIndex) => (
                      <div key={tipIndex}>
                        <Label htmlFor={`tip_line_${tipIndex}`}>Tip {tipIndex + 1}</Label>
                        <textarea
                          id={`tip_line_${tipIndex}`}
                          className="mt-1 min-h-[2.75rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
                          value={(activeTip.tips || [])[tipIndex] || ''}
                          onChange={(e) => patchTipLine(selectedTipIndex, tipIndex, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Add a tip pack to edit coaching lines.</p>
                )}
              </div>
            </div>
          ) : null}

          {section === 'options' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Visibility</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Package toggles for tenants — turn Target delivery off when selling the system without this module.
                </p>
              </div>
              <div className="space-y-3">
                <label className="flex items-start justify-between gap-3 rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">Offer to staff</p>
                    <p className="text-xs text-muted-foreground">
                      When off, hide from staff nav and home. Admins can still edit rules here.
                    </p>
                  </div>
                  <Switch
                    checked={form.staff_facing !== false}
                    onCheckedChange={(checked) => setField('staff_facing', checked)}
                  />
                </label>
                <label className="flex items-start justify-between gap-3 rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">Show on home / dashboard</p>
                    <p className="text-xs text-muted-foreground">Progress card on the main dashboard.</p>
                  </div>
                  <Switch
                    checked={Boolean(form.show_on_home)}
                    onCheckedChange={(checked) => setField('show_on_home', checked)}
                  />
                </label>
                <label className="flex items-start justify-between gap-3 rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">Login greeting</p>
                    <p className="text-xs text-muted-foreground">Progress popup when sticky notes are empty.</p>
                  </div>
                  <Switch
                    checked={Boolean(form.greet_when_no_sticky_notes)}
                    onCheckedChange={(checked) => setField('greet_when_no_sticky_notes', checked)}
                  />
                </label>
                <label className="flex items-start justify-between gap-3 rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">Year-end increment</p>
                    <p className="text-xs text-muted-foreground">Show salary growth tracking to staff.</p>
                  </div>
                  <Switch
                    checked={Boolean(form.show_year_end_increment)}
                    onCheckedChange={(checked) => setField('show_year_end_increment', checked)}
                  />
                </label>
              </div>
              {form.show_year_end_increment ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="four_star_months_required">4★ months required</Label>
                    <Input id="four_star_months_required" type="number" value={form.four_star_months_required} onChange={(e) => setField('four_star_months_required', e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="annual_avg_required">Annual average required</Label>
                    <Input id="annual_avg_required" type="number" step="0.1" value={form.annual_avg_required} onChange={(e) => setField('annual_avg_required', e.target.value)} />
                  </div>
                  <div className="sm:col-span-2">
                    <Label htmlFor="contract_line">Staff policy line</Label>
                    <textarea
                      id="contract_line"
                      className="mt-1 min-h-[3.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
                      value={form.contract_line || ''}
                      onChange={(e) => setField('contract_line', e.target.value)}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {section === 'publish' ? (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">Publish</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Saving creates a versioned rule set effective from the date you choose.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="effective_from">Effective from</Label>
                  <Input
                    id="effective_from"
                    type="date"
                    value={form.effective_from || ''}
                    onChange={(e) => setField('effective_from', e.target.value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="change_reason">Reason / comment</Label>
                  <textarea
                    id="change_reason"
                    className="mt-1 min-h-[3.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
                    value={form.change_reason || ''}
                    onChange={(e) => setField('change_reason', e.target.value)}
                    placeholder="Why these rules are changing"
                  />
                </div>
              </div>
              {Array.isArray(form.versions) && form.versions.length ? (
                <div className="space-y-2 rounded-md border p-3 text-sm">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Previous versions</p>
                  {[...form.versions].reverse().slice(0, 6).map((row) => (
                    <p key={row.id || row.saved_at}>
                      {row.effective_from || '—'} → {row.effective_until || 'now'}
                      {row.daily_target != null ? ` · target ${kes(row.daily_target)}` : ''}
                      {row.reason ? ` · ${row.reason}` : ''}
                    </p>
                  ))}
                </div>
              ) : null}
              <div className="flex justify-end">
                <Button type="submit" disabled={saving}>
                  <Save className="mr-1.5 h-4 w-4" />
                  {saving ? 'Saving…' : 'Publish performance rules'}
                </Button>
              </div>
            </div>
          ) : null}

          {section !== 'publish' ? (
            <div className="mt-4 flex items-center justify-between border-t pt-3">
              <Badge variant="secondary" className="text-[10px]">
                {selectedRole || 'No role'}
              </Badge>
              <Button type="submit" size="sm" disabled={saving}>
                <Save className="mr-1.5 h-3.5 w-3.5" />
                {saving ? 'Saving…' : 'Save'}
              </Button>
            </div>
          ) : null}
        </section>
      </div>
    </form>
  );
}
