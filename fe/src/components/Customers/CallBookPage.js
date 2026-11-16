import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Clock, Copy, PhoneOff, X } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import {
  CALL_OUTCOMES,
  WEEKDAY_LABELS,
  callCoveragePercent,
  customerCategoryLabel,
  outcomeLabel,
  weekdayLabel,
} from '../../utils/callBook';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { PageHeader, PageShell } from '../page';

const EMPTY_PLAN_ROW = { weekday: 0, county: '', sub_county: '', ward: '' };
const OUTCOME_ICON = {
  called: Check,
  ask_later: Clock,
  no_answer: PhoneOff,
  unreachable: X,
};

/**
 * Shared call centre.
 *
 * Staff copy a number and call on their own phone, then record the result.
 * Saturday and Sunday stay readable and do not offer a mark. Managers can
 * edit which wards fall on which weekday.
 */
export default function CallBookPage() {
  const [book, setBook] = useState(null);
  const [view, setView] = useState('queue');
  const [day, setDay] = useState(0);
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState(null);
  const [index, setIndex] = useState(0);
  const canEditPlan = isManagerOrAdminFromStorage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await customersAPI.callBook({
        scope: 'week',
        status: 'all',
        page_size: 1000,
      });
      setBook(data);
      setDay(data?.summary?.is_call_day ? data.summary.weekday : 0);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not open the call centre.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!canEditPlan) return undefined;
    let cancelled = false;
    customersAPI.callBookPlan().then(({ data }) => {
      if (!cancelled) setPlan(data);
    }).catch(() => {
      if (!cancelled) toast.error('Could not load the day plan.');
    });
    return () => {
      cancelled = true;
    };
  }, [canEditPlan]);

  const summary = book?.summary;
  const markingOpen = Boolean(summary?.is_call_day);
  const results = book?.results || [];
  const queue = useMemo(
    () => results.filter((row) => row.call_later_due || (row.weekday === day && !row.called_this_week)),
    [results, day],
  );
  const dayRows = useMemo(
    () => results.filter((row) => row.weekday === day),
    [results, day],
  );
  const current = queue[Math.min(index, Math.max(queue.length - 1, 0))] || null;

  return (
    <PageShell>
      <PageHeader
        eyebrow="Customers"
        title="Call centre"
        description="Copy the number and call on your phone. Then record what happened. The system does not place the call."
      />
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Call centre">
        <FilterButton active={view === 'overview'} onClick={() => setView('overview')} label="Overview" />
        <FilterButton active={view === 'week'} onClick={() => setView('week')} label="Weekly schedule" />
        <FilterButton active={view === 'queue'} onClick={() => setView('queue')} label="Call queue" />
      </div>
      {loading && <p className="text-sm text-muted-foreground">Opening the book…</p>}
      {!loading && view === 'overview' && summary && (
        <Overview summary={summary} onOpenQueue={() => { setDay(summary.weekday); setView('queue'); }} />
      )}
      {!loading && view === 'week' && summary && (
        <WeekPlan
          summary={summary}
          day={day}
          rows={dayRows}
          onDay={(next) => { setDay(next); setIndex(0); }}
          onOpen={(weekday) => { setDay(weekday); setIndex(0); setView('queue'); }}
          onSelect={(customerId) => {
            const next = results.filter((row) => (
              row.call_later_due || (row.weekday === day && !row.called_this_week)
            ));
            const at = next.findIndex((row) => row.customer_id === customerId);
            setIndex(at >= 0 ? at : 0);
            setView('queue');
          }}
        />
      )}
      {!loading && view === 'queue' && (
        <Workspace
          summary={summary}
          current={current}
          position={queue.length ? Math.min(index, queue.length - 1) + 1 : 0}
          total={queue.length}
          markingOpen={markingOpen}
          dayLabel={weekdayLabel(day)}
          onPrevious={() => setIndex((value) => Math.max(0, value - 1))}
          onSaved={() => {
            setIndex(0);
            load();
          }}
        />
      )}
      {canEditPlan && plan && view === 'week' && (
        <PlanEditor
          plan={plan}
          onChange={setPlan}
          onSaved={(next) => {
            setPlan(next);
            load();
          }}
        />
      )}
    </PageShell>
  );
}

/**
 * Week totals and a bar for each weekday.
 *
 * @param {object} props.summary API summary with days, called, and callable.
 * @param {Function} props.onOpenQueue Opens today's queue.
 */
function Overview({ summary, onOpenQueue }) {
  const percent = callCoveragePercent(summary.called, summary.callable);
  const days = summary.days || [];
  return (
    <section className="space-y-4" data-testid="call-book-counts">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Scheduled this week" value={summary.callable} hint="Customers with a number" />
        <Stat label="Recorded" value={summary.called} hint={`${percent}% of the week`} tone="text-success" />
        <Stat label="Call later" value={summary.follow_ups || 0} hint="Need another call" tone="text-warning" />
        <Stat label="Not yet called" value={summary.not_called} hint="Still on the list" tone="text-destructive" />
      </div>
      <div className="rounded-md border border-border p-3">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span>Weekly completion</span>
          <span>{summary.called} of {summary.callable} · {percent}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-success" style={{ width: `${percent}%` }} />
        </div>
        <ul className="mt-4 space-y-3">
          {days.map((item) => {
            const share = callCoveragePercent(item.called, item.callable);
            return (
              <li key={item.weekday}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{weekdayLabel(item.weekday)}</span>
                  <span className="text-muted-foreground">{item.called}/{item.callable} recorded</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-success" style={{ width: `${share}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      </div>
      <Button type="button" className="w-full" onClick={onOpenQueue}>Open call queue</Button>
    </section>
  );
}

/**
 * One number on the overview.
 *
 * @param {string} props.label Caption, at most 40 characters.
 * @param {number} props.value Count, 0 or more.
 * @param {string} props.hint Short explanation.
 * @param {string} [props.tone] Text color class.
 */
function Stat({ label, value, hint, tone = 'text-foreground' }) {
  return (
    <div className="rounded-md border border-border p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

/**
 * Monday–Friday counts and the selected day's customers.
 *
 * @param {object} props.summary Week summary.
 * @param {number} props.day Selected weekday, 0–4.
 * @param {Array} props.rows Customers on that day, at most 200.
 * @param {Function} props.onDay Selects a weekday.
 * @param {Function} props.onOpen Opens that day's queue.
 * @param {Function} props.onSelect Opens the call form for one customer id.
 */
function WeekPlan({ summary, day, rows, onDay, onOpen, onSelect }) {
  const days = summary.days || WEEKDAY_LABELS.map((label, weekday) => ({
    weekday,
    callable: 0,
    called: 0,
    not_called: 0,
    label,
  }));
  const range = summary.week_start && summary.week_end
    ? `${summary.week_start.slice(8)}–${summary.week_end.slice(8)} ${summary.week_start.slice(5, 7)}`
    : '';
  return (
    <section className="space-y-3 rounded-md border border-border p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Weekly planner</h2>
        {range && <Badge variant="secondary">{range}</Badge>}
      </div>
      <div className="grid grid-cols-5 gap-2">
        {days.map((item) => (
          <button
            key={item.weekday}
            type="button"
            className={item.weekday === day
              ? 'rounded-md bg-primary px-2 py-3 text-primary-foreground'
              : 'rounded-md px-2 py-3 text-foreground'}
            onClick={() => onDay(item.weekday)}
          >
            <span className="block text-xs">{weekdayLabel(item.weekday).slice(0, 3).toUpperCase()}</span>
            <span className="block text-xl font-semibold tabular-nums">{item.callable}</span>
            <span className="block text-xs opacity-80">Calls</span>
          </button>
        ))}
      </div>
      <h3 className="text-sm font-medium">{weekdayLabel(day)} — call schedule</h3>
      {rows.length === 0 && <p className="text-sm text-muted-foreground">No customers on this day.</p>}
      <ul className="space-y-2">
        {rows.map((row) => (
          <li key={row.customer_id} className="border-b border-border">
            <button
              type="button"
              className="flex w-full items-center justify-between gap-2 py-2 text-left"
              onClick={() => onSelect(row.customer_id)}
            >
              <span>
                <span className="block font-medium">{row.name}</span>
                <span className="block text-xs text-muted-foreground">Open to record the call</span>
              </span>
              <Badge variant={row.called_this_week ? outcomeTone(row.outcome) : 'destructive'}>
                {row.called_this_week ? outcomeLabel(row.outcome) : 'Pending'}
              </Badge>
            </button>
          </li>
        ))}
      </ul>
      <Button type="button" className="w-full" variant="outline" onClick={() => onOpen(day)}>
        Open this day's queue
      </Button>
    </section>
  );
}

/**
 * Badge tone for a stored outcome.
 *
 * @param {string} outcome Outcome key.
 * @returns {string} Badge variant.
 */
function outcomeTone(outcome) {
  return CALL_OUTCOMES.find((item) => item.value === outcome)?.tone || 'outline';
}

/**
 * One customer: copy the number, then record the cell-phone call.
 *
 * @param {object|null} props.summary Week summary.
 * @param {object|null} props.current Customer row, or null when the day is done.
 * @param {number} props.position 1-based index in the remaining queue.
 * @param {number} props.total Remaining customers on the selected day.
 * @param {boolean} props.markingOpen False on Saturday and Sunday.
 * @param {string} props.dayLabel Weekday name.
 * @param {Function} props.onPrevious Moves to the previous remaining customer.
 * @param {Function} props.onSaved Reloads after a record is saved.
 */
function Workspace({ summary, current, position, total, markingOpen, dayLabel, onPrevious, onSaved }) {
  return (
    <section className="space-y-4 rounded-md border border-border p-3" data-testid="call-workspace">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Customer call workspace</p>
          <p className="text-xs text-muted-foreground">
            {total ? `Current customer · ${position} of ${total}` : 'No customers left on this day'}
          </p>
        </div>
        <Badge variant={current?.called_this_week ? 'success' : 'warning'}>
          {current?.called_this_week ? 'Recorded' : 'Pending'}
        </Badge>
      </div>
      {!summary?.is_call_day && (
        <p className="text-sm text-muted-foreground">
          The weekend shows who was missed. Recording opens again on Monday.
        </p>
      )}
      {!current && (
        <p className="text-sm text-muted-foreground">Everyone on this day already has a result, or the list is empty.</p>
      )}
      {current && (
        <CustomerCard
          row={current}
          dayLabel={dayLabel}
          markingOpen={markingOpen}
          canGoBack={position > 1}
          onPrevious={onPrevious}
          onSaved={onSaved}
        />
      )}
    </section>
  );
}

/**
 * The customer being called, and the form that records the result.
 *
 * @param {object} props.row Book row. Phone is shown so staff can dial it themselves.
 * @param {string} props.dayLabel Scheduled weekday.
 * @param {boolean} props.markingOpen Whether a result can be saved.
 * @param {boolean} props.canGoBack Whether a previous customer is still in the queue.
 * @param {Function} props.onPrevious Goes back one customer.
 * @param {Function} props.onSaved Reloads the book.
 */
function CustomerCard({ row, dayLabel, markingOpen, canGoBack, onPrevious, onSaved }) {
  const [outcome, setOutcome] = useState('called');
  const [summary, setSummary] = useState(row.previous_summary || '');
  const [followUp, setFollowUp] = useState('');
  const [followUpTime, setFollowUpTime] = useState('');
  const [saving, setSaving] = useState(false);
  const place = [row.ward, row.sub_county, row.county].filter(Boolean).join(', ');

  const copyNumber = async () => {
    try {
      await customersAPI.holdCall(row.customer_id);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not reserve this customer.');
      return;
    }
    try {
      await navigator.clipboard.writeText(row.phone);
      toast.success('Number copied. Call from your phone, then record the result.');
    } catch (error) {
      toast.error('Could not copy the number. Read it from the screen and dial it on your phone.');
    }
  };

  const save = async () => {
    if (outcome === 'ask_later' && !followUpTime) {
      toast.error('Choose the time to call again.');
      return;
    }
    setSaving(true);
    try {
      await customersAPI.markCall(row.customer_id, {
        outcome,
        request_summary: summary,
        follow_up_on: followUp,
        follow_up_time: outcome === 'ask_later' ? followUpTime : '',
      });
      toast.success('Call recorded.');
      onSaved();
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not record this call.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid={`call-row-${row.customer_id}`}>
      <h2 className="text-xl font-semibold">{row.name}</h2>
      <p className="text-lg tabular-nums">{row.phone}</p>
      {row.call_later_due && (
        <p className="mt-2 text-sm font-medium text-warning">The time to call again has been reached.</p>
      )}
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Scheduled</dt>
          <dd>{dayLabel}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Queue</dt>
          <dd>Shared queue</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Customer category</dt>
          <dd>{customerCategoryLabel(row.buyer_segment)}</dd>
        </div>
        {place && (
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Location</dt>
            <dd className="text-right">{place}</dd>
          </div>
        )}
      </dl>
      {row.previous_summary && !row.called_this_week && (
        <p className="mt-3 text-sm">Last note: {row.previous_summary}</p>
      )}
      {row.hold && !row.hold.held_by_me && (
        <p className="mt-2 text-xs text-muted-foreground">{row.hold.held_by} is on this customer now.</p>
      )}
      <Button type="button" variant="secondary" className="mt-4 w-full" onClick={copyNumber}>
        <Copy className="h-4 w-4" aria-hidden />
        Copy phone number
      </Button>
      {markingOpen && (
        <>
          <p className="mb-2 mt-4 text-sm font-medium">Record call outcome</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {CALL_OUTCOMES.map((item) => {
              const Icon = OUTCOME_ICON[item.value];
              const selected = outcome === item.value;
              const variant = !selected
                ? 'outline'
                : item.tone === 'success' || item.tone === 'destructive'
                  ? item.tone
                  : 'default';
              return (
                <Button
                  key={item.value}
                  type="button"
                  variant={variant}
                  className={selected && item.tone === 'warning' ? 'bg-warning text-warning-foreground hover:bg-warning/90' : undefined}
                  aria-pressed={selected}
                  onClick={() => setOutcome(item.value)}
                >
                  {Icon && <Icon className="h-4 w-4" aria-hidden />}
                  {item.label}
                </Button>
              );
            })}
          </div>
          <label className="mt-4 block text-sm">
            <span className="mb-1 block text-muted-foreground">Call notes</span>
            <textarea
              className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              maxLength={500}
              aria-label={`Notes for ${row.name}`}
              placeholder="What they asked for, or why to call again"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
          </label>
          <label className="mt-3 block text-sm">
            <span className="mb-1 block text-muted-foreground">Follow-up date, if you need one</span>
            <Input
              type="date"
              aria-label={`Follow-up for ${row.name}`}
              value={followUp}
              onChange={(event) => setFollowUp(event.target.value)}
            />
          </label>
          {outcome === 'ask_later' && (
            <label className="mt-3 block text-sm">
              <span className="mb-1 block text-muted-foreground">Time to call again</span>
              <Input
                type="time"
                aria-label={`Time to call ${row.name}`}
                value={followUpTime}
                onChange={(event) => setFollowUpTime(event.target.value)}
                required
              />
            </label>
          )}
          <div className="mt-3 flex gap-2">
            {canGoBack && (
              <Button type="button" variant="outline" onClick={onPrevious}>Previous</Button>
            )}
            <Button type="button" className="flex-1" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : 'Save record'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Toggle for the three call-centre views.
 *
 * @param {boolean} props.active Whether this view is open.
 * @param {Function} props.onClick Selects the view.
 * @param {string} props.label Visible label, at most 20 characters.
 */
function FilterButton({ active, onClick, label }) {
  return (
    <Button type="button" variant={active ? 'default' : 'outline'} onClick={onClick} role="tab" aria-selected={active}>
      {label}
    </Button>
  );
}

/**
 * Manager editor for which locations fall on which weekday.
 *
 * @param {object} props.plan Current plan payload.
 * @param {Function} props.onChange Updates the draft.
 * @param {Function} props.onSaved Receives the saved plan.
 */
function PlanEditor({ plan, onChange, onSaved }) {
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await customersAPI.saveCallBookPlan(plan);
      toast.success('Call plan saved.');
      onSaved(data);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not save the call plan.');
    } finally {
      setSaving(false);
    }
  };

  const updateRow = (index, field, value) => {
    const rows = plan.rows.map((row, rowIndex) => (
      rowIndex === index ? { ...row, [field]: value } : row
    ));
    onChange({ ...plan, rows });
  };

  return (
    <section className="space-y-3 rounded-md border border-border p-3">
      <h2 className="text-base font-semibold">Day plan</h2>
      <p className="text-sm text-muted-foreground">
        Customers in one sub-county share a day. Sub-counties take turns from Monday to Friday. A saved ward row still chooses that ward's day.
      </p>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-muted-foreground">No location</span>
          <select
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            aria-label="Weekday for customers with no location"
            value={plan.unlocated_weekday}
            onChange={(event) => onChange({ ...plan, unlocated_weekday: Number(event.target.value) })}
          >
            {WEEKDAY_LABELS.map((label, index) => (
              <option key={label} value={index}>{label}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-muted-foreground">Hold minutes</span>
          <Input
            type="number"
            min={1}
            max={30}
            aria-label="Hold minutes"
            value={plan.hold_minutes}
            onChange={(event) => onChange({ ...plan, hold_minutes: Number(event.target.value) })}
          />
        </label>
      </div>
      {(plan.rows || []).map((row, index) => (
        <div key={`${row.county}-${row.ward}-${index}`} className="grid gap-2 sm:grid-cols-4">
          <select
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            aria-label={`Day for row ${index + 1}`}
            value={row.weekday}
            onChange={(event) => updateRow(index, 'weekday', Number(event.target.value))}
          >
            {WEEKDAY_LABELS.map((label, weekday) => (
              <option key={label} value={weekday}>{label}</option>
            ))}
          </select>
          <Input aria-label={`County ${index + 1}`} placeholder="County" value={row.county} onChange={(event) => updateRow(index, 'county', event.target.value)} />
          <Input aria-label={`Sub-county ${index + 1}`} placeholder="Sub-county" value={row.sub_county} onChange={(event) => updateRow(index, 'sub_county', event.target.value)} />
          <Input aria-label={`Ward ${index + 1}`} placeholder="Ward" value={row.ward} onChange={(event) => updateRow(index, 'ward', event.target.value)} />
        </div>
      ))}
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => onChange({ ...plan, rows: [...(plan.rows || []), { ...EMPTY_PLAN_ROW }] })}
        >
          Add location
        </Button>
        <Button type="button" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save plan'}
        </Button>
      </div>
    </section>
  );
}
