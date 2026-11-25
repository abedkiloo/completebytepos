import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, Clock, Copy, PhoneOff, Search, X } from 'lucide-react';

import { customersAPI } from '../../services/api';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { toast } from '../../utils/toast';
import { isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import {
  CALL_OUTCOMES,
  WEEKDAY_LABELS,
  callCoveragePercent,
  callDayPlanCounts,
  callDayPlanTicker,
  callerChangedLine,
  callerNamesLine,
  customerCategoryLabel,
  dayClaimBlockedLine,
  daySubCountyLabel,
  outcomeLabel,
  weekdayLabel,
} from '../../utils/callBook';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { PageHeader, PageShell } from '../page';

const EMPTY_PLAN_ROW = { weekday: 0, county: '', sub_county: '', ward: '' };

/**
 * Whether another person already has this customer.
 *
 * @param {object|null|undefined} row Call-book row. A missing hold is free.
 * @returns {boolean} True when the hold belongs to someone else.
 */
function takenBySomeoneElse(row) {
  return Boolean(row?.hold && !row.hold.held_by_me);
}

/**
 * Customer type line, matching the customer page.
 *
 * @param {object|null} row Call-book row.
 * @returns {string} At most 20 characters.
 */
function customerTypeLabel(row) {
  if (!row) return '';
  if (row.engagement_tier === 'prospect') return 'Registered only';
  if (row.buyer_segment === 'dormant') return 'Dormant';
  if (row.buyer_segment === 'at_risk') return 'Cooling off';
  if (row.buyer_segment === 'new') return 'New buyer';
  if (row.buyer_segment === 'champion') return 'Champion';
  if (row.engagement_tier === 'buyer') return 'Existing';
  return customerCategoryLabel(row.buyer_segment);
}

/**
 * Rows for the customer information dialog.
 *
 * @param {object|null} row Call-book row. Phone is omitted when someone else holds them.
 * @returns {Array<[string, string]>} Label and value pairs. Empty when the row is missing.
 */
function customerInformationRows(row) {
  if (!row) return [];
  const place = [row.ward, row.sub_county, row.county].filter(Boolean).join(', ') || row.city || '';
  const goods = Array.isArray(row.typical_goods) ? row.typical_goods.filter(Boolean) : [];
  const lastPurchase = row.last_purchased_at
    ? new Date(row.last_purchased_at).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'Africa/Nairobi',
    })
    : '';
  const rows = [
    ['Phone', takenBySomeoneElse(row) ? 'Held by someone else' : (row.phone || 'No number')],
    ['Customer type', customerTypeLabel(row)],
    ['Location', place || 'Not recorded'],
    ['Products of interest', goods.length ? goods.join(', ') : 'None recorded'],
    ['Last purchase', lastPurchase || 'No purchase yet'],
  ];
  if (row.owner_name) rows.push(['Owner', row.owner_name]);
  if (row.contact_person) rows.push(['Person to ask for', row.contact_person]);
  if (row.address) rows.push(['Address', row.address]);
  if (row.customer_code) rows.push(['Customer code', row.customer_code]);
  if (row.email) rows.push(['Email', row.email]);
  return rows;
}
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
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [infoRow, setInfoRow] = useState(null);
  const [dayLogDate, setDayLogDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dayLog, setDayLog] = useState(null);
  const [dayLogLoading, setDayLogLoading] = useState(false);
  const debouncedSearch = useDebouncedValue(search, 350);
  const bootDay = useRef(true);
  const canEditPlan = isManagerOrAdminFromStorage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await customersAPI.callBook({
        scope: 'week',
        status: 'not_called',
        page,
        page_size: DEFAULT_PAGE_SIZE,
        weekday: day,
        search: debouncedSearch.trim() || undefined,
      });
      setBook(data);
      if (bootDay.current) {
        bootDay.current = false;
        const nextDay = data?.summary?.is_call_day ? data.summary.weekday : 0;
        if (nextDay !== day) setDay(nextDay);
      }
      if ((data?.results || []).length === 0 && page > 1) {
        setPage((value) => Math.max(1, value - 1));
      }
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not open the call centre.');
    } finally {
      setLoading(false);
    }
  }, [day, page, debouncedSearch]);

  const loadDayLog = useCallback(async () => {
    setDayLogLoading(true);
    try {
      const { data } = await customersAPI.callBookDayLog({
        date: dayLogDate || undefined,
        page: 1,
        page_size: 200,
      });
      setDayLog(data);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not load who called that day.');
    } finally {
      setDayLogLoading(false);
    }
  }, [dayLogDate]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (view !== 'day-log') return undefined;
    loadDayLog();
    return undefined;
  }, [view, loadDayLog]);

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
  const searching = Boolean(debouncedSearch.trim());
  const remaining = useMemo(
    () => results.filter((row) => row.call_later_due || !row.called_this_week),
    [results],
  );
  const queue = searching ? results : remaining;
  const listed = Number.isFinite(Number(book?.count)) ? Number(book.count) : queue.length;
  const pageCount = Math.max(1, Math.ceil(listed / DEFAULT_PAGE_SIZE));
  const currentIndex = Math.min(index, Math.max(queue.length - 1, 0));
  const current = queue[currentIndex] || null;

  useEffect(() => {
    if (view !== 'queue' || !current || !takenBySomeoneElse(current)) return;
    const next = queue.findIndex((row) => !takenBySomeoneElse(row));
    if (next >= 0 && next !== currentIndex) setIndex(next);
  }, [view, queue, current, currentIndex]);

  useEffect(() => {
    if (view !== 'queue' || !markingOpen || !current || takenBySomeoneElse(current)) return undefined;
    if (current.hold?.held_by_me) return undefined;
    let cancelled = false;
    customersAPI.holdCall(current.customer_id).catch((error) => {
      if (cancelled || error?.response?.status !== 409) return;
      const holder = error?.response?.data?.error || 'Another staff member';
      setBook((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          results: (prev.results || []).map((row) => (
            row.customer_id === current.customer_id
              ? { ...row, hold: { held_by: holder, held_by_me: false, expires_at: '' } }
              : row
          )),
        };
      });
    });
    return () => {
      cancelled = true;
    };
  }, [view, markingOpen, current]);

  return (
    <PageShell>
      <PageHeader
        eyebrow="Customers"
        title="Call centre"
        description="Copy the number and call on your phone. Opening a customer claims them for today so only you can call them. Shops missed last week come first."
      />
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Call centre">
        <FilterButton active={view === 'overview'} onClick={() => setView('overview')} label="Overview" />
        <FilterButton active={view === 'week'} onClick={() => setView('week')} label="Weekly schedule" />
        <FilterButton active={view === 'queue'} onClick={() => setView('queue')} label="Call queue" />
        <FilterButton active={view === 'day-log'} onClick={() => setView('day-log')} label="Who called" />
      </div>
      {!loading && summary && (
        <DayPlanTicker
          summary={summary}
          day={view === 'overview' && summary.is_call_day ? summary.weekday : day}
        />
      )}
      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
            setIndex(0);
          }}
          placeholder="Name, phone, or code…"
          className="h-10 pl-9"
          aria-label="Search customers"
          data-testid="call-book-search"
        />
      </div>
      {loading && <p className="text-sm text-muted-foreground">Opening the book…</p>}
      {!loading && view === 'overview' && summary && (
        <Overview summary={summary} onOpenQueue={() => { setDay(summary.weekday); setView('queue'); }} />
      )}
      {!loading && view === 'week' && summary && (
        <WeekPlan
          summary={summary}
          day={day}
          rows={queue}
          page={page}
          pageCount={pageCount}
          total={listed}
          onDay={(next) => { setDay(next); setPage(1); setIndex(0); }}
          onPage={(next) => { setPage(next); setIndex(0); }}
          onOpen={(weekday) => { setDay(weekday); setPage(1); setIndex(0); setView('queue'); }}
          onView={setInfoRow}
          onSelect={(customerId) => {
            const row = queue.find((item) => item.customer_id === customerId);
            if (takenBySomeoneElse(row)) return;
            const at = queue.findIndex((item) => item.customer_id === customerId);
            setIndex(at >= 0 ? at : 0);
            setView('queue');
          }}
        />
      )}
      {!loading && view === 'queue' && (
        <Workspace
          summary={summary}
          current={current}
          position={queue.length ? (page - 1) * DEFAULT_PAGE_SIZE + Math.min(index, queue.length - 1) + 1 : 0}
          total={listed}
          markingOpen={markingOpen}
          day={day}
          dayLabel={weekdayLabel(day)}
          dayPlaces={daySubCountyLabel(
            (summary?.days || []).find((item) => item.weekday === day),
            12,
          )}
          onPrevious={() => setIndex((value) => Math.max(0, value - 1))}
          onSaved={() => load()}
          onView={setInfoRow}
        />
      )}
      {view === 'day-log' && (
        <DayCallLog
          date={dayLogDate}
          loading={dayLogLoading}
          log={dayLog}
          onDate={(next) => setDayLogDate(next)}
          onRefresh={loadDayLog}
        />
      )}
      <CustomerInformationDialog
        row={infoRow}
        onOpenChange={(open) => {
          if (!open) setInfoRow(null);
        }}
      />
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
 * Live day-plan ticker: called vs not called for the selected weekday.
 *
 * @param {object} props.summary Week summary with `days`.
 * @param {number} props.day Weekday 0–4 from the day plan.
 */
function DayPlanTicker({ summary, day }) {
  const counts = callDayPlanCounts(summary, day);
  if (!counts) return null;
  const label = weekdayLabel(day) || 'Today';
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
      data-testid="call-day-ticker"
      role="status"
      aria-live="polite"
    >
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label} plan
      </span>
      <span className="font-semibold tabular-nums text-success" data-testid="call-day-ticker-called">
        {counts.called} called
      </span>
      <span className="text-muted-foreground" aria-hidden="true">·</span>
      <span className="font-semibold tabular-nums text-destructive" data-testid="call-day-ticker-not-called">
        {counts.not_called} not called
      </span>
      {counts.callable > 0 && (
        <span className="text-xs text-muted-foreground tabular-nums">
          {counts.callable} on this day&apos;s plan
        </span>
      )}
    </div>
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
        <Stat label="Missed last week" value={summary.missed_last_week || 0} hint="First priority this week" tone="text-warning" />
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
                <div className="mb-1 flex justify-between gap-2 text-sm">
                  <span>
                    <span className="block">{weekdayLabel(item.weekday)}</span>
                    {daySubCountyLabel(item, 8) && (
                      <span className="block text-xs text-muted-foreground">{daySubCountyLabel(item, 8)}</span>
                    )}
                  </span>
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
 * @param {Array} props.rows Customers still to call on this page, at most 10.
 * @param {number} props.page Current page, 1 or more.
 * @param {number} props.pageCount Pages for this day.
 * @param {number} props.total Customers still to call on this day.
 * @param {Function} props.onDay Selects a weekday and returns to page 1.
 * @param {Function} props.onPage Selects a page, 1 through pageCount.
 * @param {Function} props.onOpen Opens that day's queue.
 * @param {Function} props.onSelect Opens the call form for one customer id.
 * @param {Function} props.onView Opens that customer's general information.
 */
function WeekPlan({ summary, day, rows, page, pageCount, total, onDay, onPage, onOpen, onSelect, onView }) {
  const days = summary.days || WEEKDAY_LABELS.map((label, weekday) => ({
    weekday,
    callable: 0,
    called: 0,
    not_called: 0,
    label,
  }));
  const selected = days.find((item) => item.weekday === day) || days[0];
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
            {daySubCountyLabel(item, 2) && (
              <span className="mt-1 block truncate text-[10px] leading-tight">{daySubCountyLabel(item, 2)}</span>
            )}
            <span className="block text-xl font-semibold tabular-nums">{item.not_called}</span>
            <span className="block text-xs opacity-80">Not called</span>
            <span className="mt-1 block text-[10px] opacity-80 tabular-nums">
              {item.called} called
            </span>
          </button>
        ))}
      </div>
      <h3 className="text-sm font-medium">
        {weekdayLabel(day)} — call schedule
        {daySubCountyLabel(selected, 12) && (
          <span className="mt-0.5 block font-normal text-muted-foreground">
            {daySubCountyLabel(selected, 12)}
          </span>
        )}
        <span className="mt-1 block font-normal text-muted-foreground tabular-nums">
          {callDayPlanTicker(selected, { includeCallable: true })}
        </span>
      </h3>
      {rows.length === 0 && <p className="text-sm text-muted-foreground">No customers on this day.</p>}
      <ul className="space-y-2">
        {rows.map((row) => {
          const taken = takenBySomeoneElse(row);
          return (
          <li key={row.customer_id} className="flex items-center justify-between gap-2 border-b border-border py-2">
            <button
              type="button"
              className="min-w-0 flex-1 text-left"
              aria-label={`View information for ${row.name}`}
              onClick={() => onView(row)}
            >
              <span className="block font-medium">{row.name}</span>
              <span className="block text-xs text-muted-foreground">
                {taken
                  ? dayClaimBlockedLine(row.hold)
                  : row.missed_last_week && !row.called_this_week
                    ? 'Missed last week · first priority'
                    : 'View information'}
              </span>
              {callerNamesLine(row.callers_this_week) && (
                <span className="block text-xs text-muted-foreground">
                  Called by {callerNamesLine(row.callers_this_week)}
                </span>
              )}
              {row.caller_changed && (
                <span className="block text-xs text-warning">{callerChangedLine(row)}</span>
              )}
            </button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={taken}
              aria-label={taken ? dayClaimBlockedLine(row.hold) : `Open to record the call for ${row.name}`}
              onClick={() => onSelect(row.customer_id)}
            >
              {taken ? 'Blocked' : 'Call'}
            </Button>
            <Badge variant={row.called_this_week ? outcomeTone(row.outcome) : 'destructive'}>
              {row.called_this_week ? outcomeLabel(row.outcome) : 'Pending'}
            </Badge>
          </li>
          );
        })}
      </ul>
      {total > 0 && (
        <div className="flex items-center justify-between gap-2">
          <Button type="button" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous page
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {page} of {pageCount} · {total} still to call
          </span>
          <Button type="button" variant="outline" disabled={page >= pageCount} onClick={() => onPage(page + 1)}>
            Next page
          </Button>
        </div>
      )}
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
 * @param {string} [props.dayPlaces] Sub-counties on this day, or empty.
 * @param {Function} props.onPrevious Moves to the previous remaining customer.
 * @param {Function} props.onSaved Reloads after a record is saved.
 * @param {Function} props.onView Opens this customer's general information.
 */
function Workspace({ summary, current, position, total, markingOpen, dayLabel, dayPlaces = '', day = 0, onPrevious, onSaved, onView }) {
  const dayCounts = callDayPlanCounts(summary, day);
  return (
    <section className="space-y-4 rounded-md border border-border p-3" data-testid="call-workspace">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Customer call workspace</p>
          <p className="text-sm font-medium">{dayLabel}{dayPlaces ? ` · ${dayPlaces}` : ''}</p>
          <p className="text-xs text-muted-foreground">
            {total ? `Current customer · ${position} of ${total}` : 'No customer matches'}
          </p>
          {dayCounts && (
            <p className="mt-1 text-xs font-medium tabular-nums text-foreground" data-testid="call-workspace-day-ticker">
              {callDayPlanTicker(dayCounts, { includeCallable: true })}
            </p>
          )}
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
          onView={onView}
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
 * @param {Function} props.onView Opens this customer's general information.
 */
function CustomerCard({ row, dayLabel, markingOpen, canGoBack, onPrevious, onSaved, onView }) {
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
      <button
        type="button"
        className="text-left"
        aria-label={`View information for ${row.name}`}
        onClick={() => onView(row)}
      >
        <h2 className="text-xl font-semibold">{row.name}</h2>
      </button>
      {!takenBySomeoneElse(row) && (
        <p className="text-lg tabular-nums">{row.phone}</p>
      )}
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
      {row.missed_last_week && !row.called_this_week && (
        <p className="mt-3 text-sm font-medium text-warning" data-testid="missed-last-week">
          Not called last week — first priority this week.
        </p>
      )}
      {callerNamesLine(row.callers_last_week) && (
        <p className="mt-2 text-sm text-muted-foreground">
          Last week: {callerNamesLine(row.callers_last_week)}
        </p>
      )}
      {callerNamesLine(row.callers_this_week) && (
        <p className="mt-1 text-sm text-muted-foreground">
          This week: {callerNamesLine(row.callers_this_week)}
        </p>
      )}
      {row.caller_changed && (
        <p className="mt-1 text-sm text-warning">{callerChangedLine(row)}</p>
      )}
      {row.previous_summary && !row.called_this_week && (
        <p className="mt-3 text-sm">Last note: {row.previous_summary}</p>
      )}
      {takenBySomeoneElse(row) && (
        <p className="mt-3 rounded-md border border-border bg-muted px-3 py-2 text-sm" data-testid="day-claim-blocked">
          {dayClaimBlockedLine(row.hold)}
        </p>
      )}
      {row.hold?.held_by_me && (
        <p className="mt-3 text-sm text-muted-foreground">
          You claimed this customer for today. Nobody else can call them until tomorrow.
        </p>
      )}
      {!takenBySomeoneElse(row) && (
      <Button type="button" variant="secondary" className="mt-4 w-full" onClick={copyNumber}>
        <Copy className="h-4 w-4" aria-hidden />
        Copy phone number
      </Button>
      )}
      {markingOpen && !takenBySomeoneElse(row) && (
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
 * Who called on a chosen Nairobi calendar day.
 *
 * @param {string} props.date YYYY-MM-DD value for the date input.
 * @param {boolean} props.loading Whether the log is loading.
 * @param {object|null} props.log Day-log API payload.
 * @param {Function} props.onDate Sets the date string.
 * @param {Function} props.onRefresh Reloads the log.
 */
function DayCallLog({ date, loading, log, onDate, onRefresh }) {
  const results = log?.results || [];
  const callers = log?.callers || [];
  return (
    <section className="space-y-3 rounded-md border border-border p-3" data-testid="call-day-log">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-muted-foreground">Day</span>
          <Input
            type="date"
            value={date}
            onChange={(event) => onDate(event.target.value)}
            aria-label="Day to review who called"
            data-testid="call-day-log-date"
          />
        </label>
        <Button type="button" variant="outline" onClick={onRefresh} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </Button>
      </div>
      {callers.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Callers that day: {callers.join(', ')}
        </p>
      )}
      {loading && <p className="text-sm text-muted-foreground">Loading who called…</p>}
      {!loading && results.length === 0 && (
        <p className="text-sm text-muted-foreground">No calls recorded on this day.</p>
      )}
      <ul className="space-y-2">
        {results.map((row) => (
          <li
            key={`${row.customer_id}-${row.called_at}-${row.called_by}`}
            className="border-b border-border py-2"
          >
            <span className="block font-medium">{row.name}</span>
            <span className="block text-sm text-muted-foreground">
              {row.called_by} · {outcomeLabel(row.outcome) || row.outcome}
              {row.called_at ? ` · ${new Date(row.called_at).toLocaleTimeString('en-GB', {
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Africa/Nairobi',
              })}` : ''}
            </span>
            {row.request_summary && (
              <span className="mt-1 block text-sm">{row.request_summary}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Toggle for the call-centre views.
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

/**
 * General customer information, the same facts as the customer page.
 *
 * @param {object|null} props.row Call-book row, or null when the dialog is closed.
 * @param {Function} props.onOpenChange Closes the dialog when passed false.
 */
function CustomerInformationDialog({ row, onOpenChange }) {
  const facts = customerInformationRows(row);
  return (
    <Dialog open={Boolean(row)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Customer information</DialogTitle>
          <DialogDescription>{row?.name || 'Customer'}</DialogDescription>
        </DialogHeader>
        <table className="w-full text-sm" data-testid="call-customer-info">
          <tbody>
            {facts.map(([field, value]) => (
              <tr key={field} className="border-t border-border">
                <td className="py-2 pr-3 text-muted-foreground">{field}</td>
                <td className="py-2">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <DialogFooter>
          <Button type="button" onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
