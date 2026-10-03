import React, { useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { kes } from '../../utils/appraisalStars';
import { filterRoleDailyTargets, isAppraisalAdminRole } from '../../utils/appraisalRoles';

function BandTable({ title, rows, columns, onChange, onAdd, onRemove }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <Button type="button" size="sm" variant="outline" onClick={onAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add band
        </Button>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-muted-foreground">
              {columns.map((col) => (
                <th key={col.key} className="pb-2 pr-2 font-medium">{col.label}</th>
              ))}
              <th className="pb-2 w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.min}-${index}`}>
                {columns.map((col) => (
                  <td key={col.key} className="py-1 pr-2">
                    <Input
                      type={col.type || 'number'}
                      step={col.step}
                      value={row[col.key] ?? ''}
                      onChange={(e) => onChange(index, col.key, e.target.value)}
                    />
                  </td>
                ))}
                <td className="py-1">
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
      </CardContent>
    </Card>
  );
}

function num(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

const LOCKED_ROLES = ['Manager', 'Sales Personnel', 'Field Sales'];

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

function rolePreview(form, role) {
  const fw = form.role_frameworks?.[role] || {};
  const target = num(fw.daily_target, num(form.role_daily_targets?.[role], form.daily_target));
  const bands = Array.isArray(fw.daily_star_bands) && fw.daily_star_bands.length
    ? fw.daily_star_bands
    : (form.daily_star_bands || []);
  const four = bands.find((band) => Math.abs(Number(band.stars) - 4) < 0.01);
  const five = bands.find((band) => Math.abs(Number(band.stars) - 5) < 0.01);
  const baseline = num(four?.min, form.daily_target);
  const scaled = baseline > 0 ? target / baseline : 1;
  const usesOwnBands = Array.isArray(fw.daily_star_bands) && fw.daily_star_bands.length;
  return {
    role,
    daily_target: target,
    four_star_target: usesOwnBands ? num(four?.min, target) : Math.round(num(four?.min, target) * scaled),
    five_star_target: usesOwnBands ? num(five?.min, 0) : Math.round(num(five?.min, 0) * scaled),
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
    change_reason: '',
    effective_from: '',
  }));
  const [newRole, setNewRole] = useState('');
  const [newRoleTarget, setNewRoleTarget] = useState('');
  const [selectedRole, setSelectedRole] = useState(
    () => (policy?.role_daily_targets?.['Sales Personnel'] != null ? 'Sales Personnel' : Object.keys(roleTargetsFromPolicy(policy))[0] || ''),
  );

  const dailyColumns = useMemo(
    () => [
      { key: 'min', label: 'From (KES)', step: '1' },
      { key: 'stars', label: 'Stars', step: '0.5' },
      { key: 'label', label: 'Label', type: 'text' },
    ],
    []
  );
  const bonusColumns = useMemo(
    () => [
      { key: 'min', label: 'From (KES)', step: '1' },
      { key: 'stars', label: 'Rating', step: '0.5' },
      { key: 'bonus', label: 'Bonus (KES)', step: '1' },
      { key: 'label', label: 'Label', type: 'text' },
    ],
    []
  );
  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const emptyTipPack = () => ({
    id: `pack-${Date.now()}`,
    title: '',
    why: '',
    tips: ['', '', '', '', ''],
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
      const tips = [...(next[packIndex]?.tips || ['', '', '', '', ''])];
      while (tips.length < 5) tips.push('');
      tips[tipIndex] = value;
      next[packIndex] = { ...next[packIndex], tips };
      return { ...prev, daily_tip_packs: next };
    });
  };

  const patchBand = (listKey, index, key, value) => {
    setForm((prev) => {
      const next = [...(prev[listKey] || [])];
      next[index] = { ...next[index], [key]: key === 'label' ? value : num(value, next[index][key]) };
      return { ...prev, [listKey]: next };
    });
  };

  const roleTargets = form.role_daily_targets || {};
  const roleNames = Object.keys(roleTargets).sort((a, b) => a.localeCompare(b));
  const preview = selectedRole ? rolePreview(form, selectedRole) : null;
  const selectedFramework = selectedRole
    ? { ...frameworkFromPolicy(form, selectedRole), ...(form.role_frameworks?.[selectedRole] || {}) }
    : null;

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
      )
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
      show_year_end_increment: Boolean(form.show_year_end_increment),
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

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Performance rules</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Choose a role, then set its salary, daily target, stars, monthly bonus, and annual increment. Saving publishes a versioned rule set.
          </p>
          <div>
            <Label htmlFor="selected_role">Role</Label>
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
          {selectedFramework ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <Label htmlFor="fw_basic">Basic salary</Label>
                <Input id="fw_basic" type="number" value={selectedFramework.basic_pay ?? ''} onChange={(e) => patchFramework(selectedRole, 'basic_pay', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="fw_target">Daily target</Label>
                <Input id="fw_target" type="number" value={selectedFramework.daily_target ?? ''} onChange={(e) => patchFramework(selectedRole, 'daily_target', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="fw_increment">Annual increment</Label>
                <Input id="fw_increment" type="number" value={selectedFramework.year_end_increment ?? ''} onChange={(e) => patchFramework(selectedRole, 'year_end_increment', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="fw_days">Working days</Label>
                <Input id="fw_days" type="number" value={selectedFramework.working_days ?? ''} onChange={(e) => patchFramework(selectedRole, 'working_days', e.target.value)} />
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {preview ? (
        <Card data-testid="appraisal-rules-preview">
          <CardHeader>
            <CardTitle className="text-base">Preview · {preview.role}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
            <p>Daily target <span className="font-semibold">{kes(preview.daily_target)}</span></p>
            <p>4-Star target <span className="font-semibold">{kes(preview.four_star_target)}</span></p>
            <p>5-Star target <span className="font-semibold">{preview.five_star_target ? `${kes(preview.five_star_target)}+` : '—'}</span></p>
            <p>Monthly 4-Star requirement <span className="font-semibold">{Number(preview.four_star_month_min_avg).toFixed(1)} average</span></p>
            <p>Annual requirement <span className="font-semibold">{Number(preview.annual_avg_required).toFixed(1)} average · {preview.four_star_months_required} 4-Star months</span></p>
            <p>Annual increment <span className="font-semibold">{kes(preview.year_end_increment)}</span></p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pay and qualification</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="basic_pay">Basic pay (KES)</Label>
            <Input id="basic_pay" type="number" value={form.basic_pay} onChange={(e) => setField('basic_pay', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="working_days">Working days / month</Label>
            <Input id="working_days" type="number" value={form.working_days} onChange={(e) => setField('working_days', e.target.value)} />
          </div>
          {form.show_year_end_increment ? (
            <>
              <div>
                <Label htmlFor="year_end_increment">Year-end increment (KES)</Label>
                <Input id="year_end_increment" type="number" value={form.year_end_increment} onChange={(e) => setField('year_end_increment', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="four_star_months_required">4-star months required</Label>
                <Input id="four_star_months_required" type="number" value={form.four_star_months_required} onChange={(e) => setField('four_star_months_required', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="annual_avg_required">Annual average required</Label>
                <Input id="annual_avg_required" type="number" step="0.1" value={form.annual_avg_required} onChange={(e) => setField('annual_avg_required', e.target.value)} />
              </div>
            </>
          ) : null}
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Switch
              checked={Boolean(form.greet_when_no_sticky_notes)}
              onCheckedChange={(checked) => setField('greet_when_no_sticky_notes', checked)}
            />
            Greet with progress when there are no sticky notes
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch
              checked={Boolean(form.show_on_home)}
              onCheckedChange={(checked) => setField('show_on_home', checked)}
            />
            Show on home / dashboard
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Switch
              checked={Boolean(form.show_year_end_increment)}
              onCheckedChange={(checked) => setField('show_year_end_increment', checked)}
            />
            Show year-end increment to staff
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Daily targets by role</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Each manager and sales role has its own daily target. 4-star “target met” scales with the amount you set. Admin roles are not scored.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {roleNames.map((role) => (
              <div key={role}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <Label htmlFor={`role_target_${role}`}>{role}</Label>
                  {!LOCKED_ROLES.includes(role) ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label={`Remove ${role}`}
                      onClick={() => removeRoleTarget(role)}
                    >
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
          <div className="grid gap-2 sm:grid-cols-[1fr_8rem_auto]">
            <Input
              placeholder="Add another role…"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              aria-label="New role name"
            />
            <Input
              type="number"
              placeholder="KES"
              value={newRoleTarget}
              onChange={(e) => setNewRoleTarget(e.target.value)}
              aria-label="New role daily target"
            />
            <Button type="button" variant="outline" onClick={addRoleTarget}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              Add role
            </Button>
          </div>
        </CardContent>
      </Card>

      <BandTable
        title="Daily star rating (defaults)"
        rows={form.daily_star_bands || []}
        columns={dailyColumns}
        onChange={(i, k, v) => patchBand('daily_star_bands', i, k, v)}
        onAdd={() => setField('daily_star_bands', [...(form.daily_star_bands || []), { min: 0, stars: 1, label: '' }])}
        onRemove={(i) => setField('daily_star_bands', (form.daily_star_bands || []).filter((_, idx) => idx !== i))}
      />

      {selectedRole ? (
        <BandTable
          title={`Daily star rating · ${selectedRole}`}
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
      ) : null}

      <BandTable
        title="Monthly bonus (defaults)"
        rows={form.monthly_bonus_bands || []}
        columns={bonusColumns}
        onChange={(i, k, v) => patchBand('monthly_bonus_bands', i, k, v)}
        onAdd={() => setField('monthly_bonus_bands', [...(form.monthly_bonus_bands || []), { min: 0, stars: 1, bonus: 0, label: '' }])}
        onRemove={(i) => setField('monthly_bonus_bands', (form.monthly_bonus_bands || []).filter((_, idx) => idx !== i))}
      />

      {selectedRole ? (
        <BandTable
          title={`Monthly bonus · ${selectedRole}`}
          rows={selectedFramework?.monthly_bonus_bands || []}
          columns={bonusColumns}
          onChange={(i, k, v) => patchFrameworkBand(selectedRole, 'monthly_bonus_bands', i, k, v)}
          onAdd={() => patchFramework(selectedRole, 'monthly_bonus_bands', [...(selectedFramework?.monthly_bonus_bands || []), { min: 0, stars: 1, bonus: 0, label: '' }])}
          onRemove={(i) => patchFramework(
            selectedRole,
            'monthly_bonus_bands',
            (selectedFramework?.monthly_bonus_bands || []).filter((_, idx) => idx !== i),
          )}
        />
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">Daily sales tips</CardTitle>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setField('daily_tip_packs', [...(form.daily_tip_packs || []), emptyTipPack()])}
          >
            <Plus className="mr-1 h-3.5 w-3.5" />
            Add pack
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            One pack of five tips shows each day in the greeting. Paste follow-up, conversation, and new-customer tips here.
          </p>
          {(form.daily_tip_packs || []).map((pack, packIndex) => (
            <div key={pack.id || packIndex} className="space-y-2 rounded-md border p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="grid flex-1 gap-2 sm:grid-cols-2">
                  <div>
                    <Label htmlFor={`tip_title_${packIndex}`}>Title</Label>
                    <Input
                      id={`tip_title_${packIndex}`}
                      value={pack.title || ''}
                      onChange={(e) => patchTipPack(packIndex, 'title', e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor={`tip_why_${packIndex}`}>Why it matters</Label>
                    <Input
                      id={`tip_why_${packIndex}`}
                      value={pack.why || ''}
                      onChange={(e) => patchTipPack(packIndex, 'why', e.target.value)}
                    />
                  </div>
                </div>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove tip pack ${packIndex + 1}`}
                  onClick={() => setField(
                    'daily_tip_packs',
                    (form.daily_tip_packs || []).filter((_, idx) => idx !== packIndex),
                  )}
                  disabled={(form.daily_tip_packs || []).length <= 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              {[0, 1, 2, 3, 4].map((tipIndex) => (
                <div key={tipIndex}>
                  <Label htmlFor={`tip_${packIndex}_${tipIndex}`}>Tip {tipIndex + 1}</Label>
                  <textarea
                    id={`tip_${packIndex}_${tipIndex}`}
                    className="min-h-[3.25rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
                    value={(pack.tips || [])[tipIndex] || ''}
                    onChange={(e) => patchTipLine(packIndex, tipIndex, e.target.value)}
                  />
                </div>
              ))}
            </div>
          ))}
        </CardContent>
      </Card>

      {form.show_year_end_increment ? (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Staff policy line</CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="contract_line">Year-end increment</Label>
          <textarea
            id="contract_line"
            className="min-h-[4.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
            value={form.contract_line || ''}
            onChange={(e) => setField('contract_line', e.target.value)}
          />
        </CardContent>
      </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Effective date</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
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
              className="min-h-[3.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
              value={form.change_reason || ''}
              onChange={(e) => setField('change_reason', e.target.value)}
              placeholder="Why these rules are changing"
            />
          </div>
        </CardContent>
      </Card>

      {Array.isArray(form.versions) && form.versions.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Previous versions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[...form.versions].reverse().slice(0, 8).map((row) => (
              <p key={row.id || row.saved_at}>
                {row.effective_from || '—'} → {row.effective_until || 'now'}
                {row.daily_target != null ? ` · target ${kes(row.daily_target)}` : ''}
                {row.reason ? ` · ${row.reason}` : ''}
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Publish performance rules'}
        </Button>
      </div>
    </form>
  );
}
