import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { cn } from '../../lib/cn';
import { appraisalTone, kes, MONTH_NAMES, starGlyphs } from '../../utils/appraisalStars';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import AppraisalDailyTips from './AppraisalDailyTips';
import AppraisalProgressBar from './AppraisalProgressBar';

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

function weekday(iso) {
  if (!iso) return '';
  const date = new Date(`${iso}T12:00:00`);
  return Number.isNaN(date.getTime()) ? '' : WEEKDAYS[date.getDay()];
}

function StarRow({ stars, className }) {
  return (
    <span className={cn('tracking-tight', className)} aria-label={`${stars} stars`}>
      {starGlyphs(stars)}
    </span>
  );
}

function Metric({ label, value, hint, tone }) {
  const theme = appraisalTone(tone);
  return (
    <div>
      <p className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className={cn('mt-1 text-xl font-extrabold tabular-nums sm:text-2xl', theme.text)}>{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function TodayCard({ today }) {
  const theme = appraisalTone(today?.tone);
  const remaining = Number(today?.amount_to_target || 0);
  const toFour = Number(today?.amount_to_next || remaining);
  const stars = Number(today?.stars || 1);
  return (
    <Card className={cn('overflow-hidden border-2', theme.border, theme.bg)} data-testid="appraisal-today">
      <CardContent className="space-y-4 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-muted-foreground">
              Today
            </p>
            <p className={cn('mt-1 text-3xl font-extrabold tabular-nums sm:text-4xl', theme.text)}>
              {kes(today?.sales)}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Target {kes(today?.target)}
            </p>
          </div>
          <div className="text-right">
            <StarRow stars={stars} className="text-2xl text-amber-500" />
            <p className={cn('mt-1 text-sm font-semibold', theme.text)}>
              {today?.status_label || today?.label || ''}
            </p>
          </div>
        </div>
        <AppraisalProgressBar
          progress={today?.target_progress}
          tone={today?.tone}
          label="Daily target"
        />
        <p
          className={cn(
            'rounded-lg px-3 py-2 text-center text-sm font-bold sm:text-base',
            remaining > 0 ? 'bg-background/80' : cn(theme.pill),
          )}
          data-testid="appraisal-remaining"
        >
          {remaining > 0
            ? `${kes(stars >= 4 ? toFour : remaining)} more to reach ${stars >= 4 ? '5 Stars' : '4 Stars'}`
            : 'Daily target achieved'}
        </p>
      </CardContent>
    </Card>
  );
}

function MonthCard({ month, policy }) {
  const expected = Number(month?.expected_sales || 0);
  const sales = Number(month?.sales || 0);
  const pct = expected > 0 ? sales / expected : 0;
  const avg = Number(month?.official_average || 0);
  const needed = Number(policy?.four_star_month_min_avg || 4);
  return (
    <Card data-testid="appraisal-month">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Monthly performance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric label="Sales" value={kes(sales)} hint={expected ? `of ${kes(expected)}` : ''} tone={month?.tone} />
          <Metric label="Pace" value={`${Math.round(pct * 1000) / 10}%`} tone={month?.tone} />
          <Metric
            label="Average"
            value={`${avg.toFixed(2)}`}
            hint={`Need ${needed.toFixed(1)} for a 4-Star month`}
            tone={month?.four_star_month ? 'emerald' : month?.tone}
          />
          <Metric
            label="4-Star days"
            value={`${month?.four_star_days || 0}`}
            hint={`${month?.days_elapsed || 0} of ${month?.working_days || 0} days`}
            tone={month?.tone}
          />
        </div>
        <AppraisalProgressBar progress={pct} tone={month?.tone} label="Expected monthly sales" />
        <p className="text-xs text-muted-foreground">
          {month?.days_remaining || 0} working days remaining
          {month?.four_star_month_eligible === false
            ? ' · Incomplete first cycle — recorded, not eligible for 4-Star month qualification'
            : ''}
        </p>
      </CardContent>
    </Card>
  );
}

function BonusLadder({ month, bands, bonusMinStars = 4 }) {
  const sales = Number(month?.sales || 0);
  const current = Number(month?.bonus || 0);
  const next = month?.next_bonus;
  const toNext = Number(month?.amount_to_next_bonus || 0);
  const rows = Array.isArray(bands) ? [...bands].sort((a, b) => Number(a.min) - Number(b.min)) : [];
  const paidRows = rows.filter(
    (band) => Number(band.stars || 0) >= Number(bonusMinStars || 4) || Number(band.bonus || 0) > 0,
  );
  return (
    <Card data-testid="appraisal-bonus">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Monthly bonus</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Cash starts at {Number(bonusMinStars || 4)}★ (KES 2,000 base). Higher sales unlock more, up to the role cap.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Metric label="Current sales" value={kes(sales)} tone={month?.tone} />
          <Metric label="Current bonus" value={kes(current)} tone={current ? 'emerald' : 'rose'} />
          <Metric
            label="Next bonus"
            value={toNext > 0 ? kes(next) : 'Max reached'}
            hint={toNext > 0 ? `${kes(toNext)} more to unlock` : ''}
            tone={toNext > 0 ? 'amber' : 'gold'}
          />
        </div>
        <ol className="space-y-2">
          {(paidRows.length ? paidRows : rows).map((band) => {
            const unlocked = sales >= Number(band.min || 0);
            const pays = Number(band.bonus || 0) > 0;
            return (
              <li
                key={`${band.min}-${band.stars}`}
                className={cn(
                  'flex items-center justify-between rounded-lg border px-3 py-2 text-sm',
                  unlocked && pays ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30' : 'border-border',
                )}
              >
                <span className="font-medium">
                  {starGlyphs(band.stars)} · {kes(band.min)}+
                </span>
                <span className="tabular-nums font-semibold">
                  {pays ? kes(band.bonus) : 'No cash yet'}
                </span>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

function SalaryCard({ year, policy }) {
  if (!policy?.show_year_end_increment) return null;
  const have = Number(year?.four_star_months || 0);
  const need = Number(year?.four_star_months_required || 8);
  const annual = Number(year?.ytd_average || year?.annual_average || 0);
  const required = Number(policy?.annual_avg_required || 4);
  const increment = Number(policy?.year_end_increment || 0);
  const basic = Number(year?.basic_pay || policy?.basic_pay || 0);
  return (
    <Card data-testid="appraisal-salary">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Your salary growth</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Current basic" value={kes(basic)} tone="teal" />
          <Metric label="Potential next basic" value={kes(basic + increment)} tone="gold" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Annual average" value={`${annual.toFixed(2)} / ${required.toFixed(2)}`} tone={year?.tone} />
          <Metric label="4-Star months" value={`${have} / ${need}`} tone={year?.tone} />
        </div>
        <AppraisalProgressBar progress={year?.progress_to_increment} tone={year?.qualifies ? 'gold' : year?.tone} label={`${have} of ${need} months`} />
        {year?.increment_message ? (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            {year.increment_message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DayStrip({ days, dayHref }) {
  const rows = Array.isArray(days) ? days.slice(-14) : [];
  if (!rows.length) return null;
  return (
    <Card data-testid="appraisal-calendar">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Daily performance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {rows.map((day) => {
            const theme = appraisalTone(day.tone);
            const tileClass = cn('min-w-[4.75rem] rounded-lg border p-2 text-center', theme.border, theme.bg);
            const body = (
              <>
                <p className="text-[10px] font-bold uppercase text-muted-foreground">{weekday(day.date)}</p>
                <p className="text-xs font-semibold tabular-nums">{kes(day.sales).replace('KES ', '')}</p>
                <StarRow stars={day.stars} className="text-sm text-amber-500" />
              </>
            );
            if (dayHref && day.date) {
              return (
                <Link
                  key={day.date}
                  to={dayHref(day.date)}
                  className={cn(tileClass, 'transition hover:ring-2 hover:ring-primary/40')}
                  aria-label={`Open sales for ${day.date}`}
                >
                  {body}
                </Link>
              );
            }
            return (
              <div key={day.date} className={tileClass}>
                {body}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function TrendChart({ days, target }) {
  const data = useMemo(
    () => (Array.isArray(days) ? days.map((day) => ({
      date: weekday(day.date) || day.date,
      sales: Number(day.sales || 0),
      target: Number(target || 0),
    })) : []),
    [days, target],
  );
  if (data.length < 2) return null;
  return (
    <Card data-testid="appraisal-trend">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Daily sales vs target</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(value) => kes(value)} />
            <Line type="monotone" dataKey="sales" stroke="#059669" strokeWidth={2} dot={false} name="Sales" />
            <Line type="monotone" dataKey="target" stroke="#d97706" strokeWidth={2} strokeDasharray="4 4" dot={false} name="Target" />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export default function AppraisalDashboard({ snapshot, dayHref }) {
  if (!snapshot || snapshot.has_personal_target === false) return null;
  const { today, month, year, greeting, policy, today_tips: todayTips } = snapshot;
  return (
    <div className="space-y-4" data-testid="appraisal-dashboard">
      {greeting?.headline ? (
        <div>
          <h2 className="text-xl font-extrabold leading-tight sm:text-2xl">{greeting.headline}</h2>
          {greeting.detail ? (
            <p className="mt-1 text-sm text-muted-foreground">{greeting.detail}</p>
          ) : null}
        </div>
      ) : null}
      <TodayCard today={today} />
      <MonthCard month={month} policy={policy} />
      <BonusLadder
        month={month}
        bands={policy?.monthly_bonus_bands}
        bonusMinStars={policy?.bonus_min_stars}
      />
      <SalaryCard year={year} policy={policy} />
      <DayStrip days={month?.days} dayHref={dayHref} />
      <TrendChart days={month?.days} target={today?.target} />
      {policy?.show_year_end_increment && Array.isArray(year?.months) ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">This year</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 lg:grid-cols-12">
              {year.months.map((row) => {
                const theme = appraisalTone(row.tone);
                return (
                  <div key={row.month} className={cn('rounded-md border p-2 text-center', theme.border, theme.bg)}>
                    <p className="text-[11px] uppercase text-muted-foreground">{MONTH_NAMES[row.month - 1]}</p>
                    <p className={cn('text-sm font-semibold', theme.text)}>
                      {Number(row.official_average || 0).toFixed(1)}
                    </p>
                    <p className="text-[11px]">{row.four_star_month ? '4★ month' : '—'}</p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ) : null}
      <AppraisalDailyTips pack={todayTips} />
    </div>
  );
}
