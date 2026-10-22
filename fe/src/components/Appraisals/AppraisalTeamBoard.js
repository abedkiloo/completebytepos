import React, { useMemo, useState } from 'react';

import { cn } from '../../lib/cn';
import { appraisalTone, kes, starGlyphs } from '../../utils/appraisalStars';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { EmptyState } from '../page';
import { ListSortBar } from '../page/ListSortBar';
import { useListOrdering } from '../../hooks/useListOrdering';
import { sortRecords } from '../../utils/listOrdering';
import AppraisalProgressBar from './AppraisalProgressBar';

function monthCollection(row) {
  const sold = Number(row?.month?.collection_sold ?? row?.month?.sales ?? 0);
  const collected = Number(row?.month?.collection_collected ?? 0);
  const notCollected = Math.max(0, sold - collected);
  const pct =
    sold > 0
      ? Math.round((Math.min(collected, sold) / sold) * 100)
      : Number(row?.month?.collection_ratio || 0) * 100;
  return { sold, collected, notCollected, pct: Math.round(pct) };
}

function InsightGrid({ insights }) {
  if (!insights) return null;
  const items = [
    { label: 'Today’s sales', value: kes(insights.total_today_sales) },
    { label: 'Monthly sales', value: kes(insights.total_month_sales) },
    { label: 'Avg stars', value: Number(insights.average_stars_today || 0).toFixed(2) },
    { label: 'Hitting target', value: insights.hitting_target_today || 0 },
    { label: 'Below target', value: insights.below_target_today || 0 },
    { label: '4-Star today', value: insights.four_star_today || 0 },
    { label: 'Monthly bonuses', value: kes(insights.total_monthly_bonus) },
    { label: 'Projected increments', value: insights.projected_increments || 0 },
    { label: 'Close to increment', value: insights.close_to_increment || 0 },
    { label: 'At risk', value: insights.at_risk || 0 },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-testid="appraisal-insights">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="p-3">
            <p className="text-[11px] font-extrabold uppercase tracking-[0.12em] text-muted-foreground">
              {item.label}
            </p>
            <p className="mt-1 text-lg font-bold tabular-nums">{item.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function exportCsv(rows) {
  const header = [
    'Employee',
    'Role',
    'Today',
    'Monthly Sales',
    'Collected',
    'Not collected',
    'Collection %',
    'Avg Stars',
    'Bonus',
    '4-Star Months',
    'Annual Status',
  ];
  const lines = [header.join(',')].concat(
    rows.map((row) => {
      const mix = monthCollection(row);
      return [
        JSON.stringify(row.staff?.name || ''),
        JSON.stringify(row.staff?.role || ''),
        row.today?.sales || 0,
        row.month?.sales || 0,
        mix.collected,
        mix.notCollected,
        mix.pct,
        Number(row.month?.official_average || 0).toFixed(2),
        row.month?.bonus || 0,
        `${row.year?.four_star_months || 0}/${row.year?.four_star_months_required || 8}`,
        row.annual_status || '',
      ].join(',');
    }),
  );
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'target-delivery.csv';
  link.click();
  URL.revokeObjectURL(url);
}

export default function AppraisalTeamBoard({ team, showIncrement }) {
  const results = team?.results || [];
  const insights = team?.insights;
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('all');
  const [star, setStar] = useState('all');
  const [status, setStatus] = useState('all');
  const { ordering, setOrdering } = useListOrdering();

  const roles = useMemo(
    () => Array.from(new Set(results.map((row) => row.staff?.role).filter(Boolean))).sort(),
    [results],
  );

  const filtered = results.filter((row) => {
    const name = (row.staff?.name || '').toLowerCase();
    if (query && !name.includes(query.toLowerCase())) return false;
    if (role !== 'all' && row.staff?.role !== role) return false;
    const stars = Number(row.today?.stars || 0);
    if (star === '4+' && stars < 4) return false;
    if (star === 'below' && stars >= 4) return false;
    if (status !== 'all' && row.annual_status !== status) return false;
    return true;
  });

  const ranked = useMemo(
    () => sortRecords(
      filtered.map((row) => ({ ...row, name: row.staff?.name || '' })),
      ordering,
    ),
    [filtered, ordering],
  );

  if (!results.length) {
    return (
      <EmptyState
        title="No posted sales yet"
        description="Team target delivery appears once staff close sales this year."
      />
    );
  }

  return (
    <div className="space-y-4">
      <InsightGrid insights={insights} />
      {Array.isArray(insights?.lines) && insights.lines.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Insights</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            {insights.lines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search employee"
          aria-label="Search employee"
        />
        <select
          className="h-10 rounded-md border bg-background px-3 text-sm"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          aria-label="Filter by role"
        >
          <option value="all">All roles</option>
          {roles.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <select
          className="h-10 rounded-md border bg-background px-3 text-sm"
          value={star}
          onChange={(e) => setStar(e.target.value)}
          aria-label="Filter by stars"
        >
          <option value="all">All stars</option>
          <option value="4+">4 Stars or above</option>
          <option value="below">Below target</option>
        </select>
        <select
          className="h-10 rounded-md border bg-background px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by annual status"
        >
          <option value="all">All annual status</option>
          <option value="On track">On track</option>
          <option value="Close">Close</option>
          <option value="At risk">At risk</option>
        </select>
        <ListSortBar value={ordering} onChange={setOrdering} />
        <Button type="button" variant="outline" onClick={() => exportCsv(ranked)}>
          Export
        </Button>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full min-w-[56rem] text-sm">
          <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Employee</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Today</th>
              <th className="px-3 py-2 font-medium">Monthly sales</th>
              <th className="px-3 py-2 font-medium">Collected</th>
              <th className="px-3 py-2 font-medium">Not collected</th>
              <th className="px-3 py-2 font-medium">Collection %</th>
              <th className="px-3 py-2 font-medium">Avg stars</th>
              <th className="px-3 py-2 font-medium">Bonus</th>
              {showIncrement ? <th className="px-3 py-2 font-medium">4-Star months</th> : null}
              {showIncrement ? <th className="px-3 py-2 font-medium">Annual status</th> : null}
            </tr>
          </thead>
          <tbody>
            {ranked.map((row) => {
              const theme = appraisalTone(row.today?.tone);
              const mix = monthCollection(row);
              return (
                <tr key={row.staff.id} className="border-t">
                  <td className="px-3 py-2 font-medium">{row.staff.name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.staff.role || '—'}</td>
                  <td className="px-3 py-2">
                    <span className={cn('font-semibold', theme.text)}>
                      {kes(row.today?.sales)} {starGlyphs(row.today?.stars)}
                    </span>
                  </td>
                  <td className="px-3 py-2 tabular-nums">{kes(row.month?.sales)}</td>
                  <td className="px-3 py-2 tabular-nums text-emerald-700 dark:text-emerald-400">
                    {kes(mix.collected)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-rose-700 dark:text-rose-400">
                    {kes(mix.notCollected)}
                  </td>
                  <td className="px-3 py-2 font-medium tabular-nums">{mix.pct}%</td>
                  <td className="px-3 py-2 tabular-nums">{Number(row.month?.official_average || 0).toFixed(2)}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {kes(row.month?.bonus)}
                    {row.month?.bonus_qualified === false &&
                    Number(row.month?.bonus_earned || 0) > 0 ? (
                      <span
                        className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-amber-700"
                        title={(row.month?.bonus_block_reasons || []).join(' ')}
                      >
                        held
                      </span>
                    ) : null}
                  </td>
                  {showIncrement ? (
                    <td className="px-3 py-2">
                      {row.year?.four_star_months}/{row.year?.four_star_months_required}
                    </td>
                  ) : null}
                  {showIncrement ? (
                    <td className="px-3 py-2">{row.annual_status || '—'}</td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="space-y-3 lg:hidden">
        {ranked.map((row) => {
          const theme = appraisalTone(row.today?.tone);
          const mix = monthCollection(row);
          return (
            <Card key={`m-${row.staff.id}`} className={cn('border', theme.border)}>
              <CardContent className="space-y-2 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">{row.staff.name}</p>
                    <p className="text-xs text-muted-foreground">{row.staff.role}</p>
                  </div>
                  <span className="text-sm font-semibold">{starGlyphs(row.today?.stars)}</span>
                </div>
                <p className="text-sm">Today {kes(row.today?.sales)} · Month {kes(row.month?.sales)}</p>
                <p className="text-xs text-muted-foreground">
                  Collected {kes(mix.collected)} · Not collected {kes(mix.notCollected)} ·{' '}
                  <span className="font-semibold text-foreground">{mix.pct}%</span>
                </p>
                <AppraisalProgressBar progress={row.month?.progress_to_four_star} tone={row.month?.tone} label="4-star month" />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
