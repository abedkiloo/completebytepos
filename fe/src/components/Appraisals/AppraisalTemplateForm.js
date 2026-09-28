import React, { useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';

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

export default function AppraisalTemplateForm({ policy, saving, onSave }) {
  const [form, setForm] = useState(() => ({ ...policy }));

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
      { key: 'stars', label: 'Stars', step: '0.5' },
      { key: 'bonus', label: 'Bonus (KES)', step: '1' },
      { key: 'label', label: 'Label', type: 'text' },
    ],
    []
  );

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const patchBand = (listKey, index, key, value) => {
    setForm((prev) => {
      const next = [...(prev[listKey] || [])];
      next[index] = { ...next[index], [key]: key === 'label' ? value : num(value, next[index][key]) };
      return { ...prev, [listKey]: next };
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...form,
      basic_pay: num(form.basic_pay),
      daily_target: num(form.daily_target),
      year_end_increment: num(form.year_end_increment),
      working_days: num(form.working_days, 26),
      four_star_month_min_avg: num(form.four_star_month_min_avg, 4),
      four_star_months_required: num(form.four_star_months_required, 8),
      annual_avg_required: num(form.annual_avg_required, 4),
    });
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
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
            <Label htmlFor="daily_target">Daily target (KES)</Label>
            <Input id="daily_target" type="number" value={form.daily_target} onChange={(e) => setField('daily_target', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="year_end_increment">Year-end increment (KES)</Label>
            <Input id="year_end_increment" type="number" value={form.year_end_increment} onChange={(e) => setField('year_end_increment', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="working_days">Working days / month</Label>
            <Input id="working_days" type="number" value={form.working_days} onChange={(e) => setField('working_days', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="four_star_months_required">4-star months required</Label>
            <Input id="four_star_months_required" type="number" value={form.four_star_months_required} onChange={(e) => setField('four_star_months_required', e.target.value)} />
          </div>
          <div>
            <Label htmlFor="annual_avg_required">Annual average required</Label>
            <Input id="annual_avg_required" type="number" step="0.1" value={form.annual_avg_required} onChange={(e) => setField('annual_avg_required', e.target.value)} />
          </div>
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
        </CardContent>
      </Card>

      <BandTable
        title="Daily star bands"
        rows={form.daily_star_bands || []}
        columns={dailyColumns}
        onChange={(i, k, v) => patchBand('daily_star_bands', i, k, v)}
        onAdd={() => setField('daily_star_bands', [...(form.daily_star_bands || []), { min: 0, stars: 1, label: '' }])}
        onRemove={(i) => setField('daily_star_bands', (form.daily_star_bands || []).filter((_, idx) => idx !== i))}
      />
      <BandTable
        title="Monthly bonus bands"
        rows={form.monthly_bonus_bands || []}
        columns={bonusColumns}
        onChange={(i, k, v) => patchBand('monthly_bonus_bands', i, k, v)}
        onAdd={() => setField('monthly_bonus_bands', [...(form.monthly_bonus_bands || []), { min: 0, stars: 1, bonus: 0, label: '' }])}
        onRemove={(i) => setField('monthly_bonus_bands', (form.monthly_bonus_bands || []).filter((_, idx) => idx !== i))}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Staff policy lines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label htmlFor="contract_line">Year-end increment</Label>
            <textarea
              id="contract_line"
              className="min-h-[4.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
              value={form.contract_line || ''}
              onChange={(e) => setField('contract_line', e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="bonus_policy_line">Monthly bonus</Label>
            <textarea
              id="bonus_policy_line"
              className="min-h-[4.5rem] w-full rounded-md border bg-background px-2.5 py-2 text-sm"
              value={form.bonus_policy_line || ''}
              onChange={(e) => setField('bonus_policy_line', e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save template'}
        </Button>
      </div>
    </form>
  );
}
