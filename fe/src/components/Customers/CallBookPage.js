import React, { useCallback, useEffect, useState } from 'react';

import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import {
  CALL_OUTCOMES,
  callBookCountLine,
  outcomeLabel,
  weekdayLabel,
} from '../../utils/callBook';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { PageHeader, PageShell } from '../page';

const EMPTY_PLAN_ROW = { weekday: 0, county: '', sub_county: '', ward: '' };

/**
 * Weekly shared call book.
 *
 * Opens on customers who have not been called this week. Saturday and
 * Sunday stay readable and do not offer a mark. Managers can edit which
 * wards fall on which weekday.
 */
export default function CallBookPage() {
  const [book, setBook] = useState(null);
  const [scope, setScope] = useState('today');
  const [status, setStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState(null);
  const [savingId, setSavingId] = useState(null);
  const canEditPlan = isManagerOrAdminFromStorage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await customersAPI.callBook({ scope, status, page_size: 200 });
      setBook(data);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not open the call book.');
    } finally {
      setLoading(false);
    }
  }, [scope, status]);

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

  return (
    <PageShell>
      <PageHeader
        eyebrow="Customers"
        title="Call book"
        description="Monday to Friday. Open the list, call the number, then mark it with what they asked for. Ask later still counts for this week."
      />
      {summary && (
        <p className="text-sm text-foreground" data-testid="call-book-counts">
          {callBookCountLine(summary)}
          {summary.is_call_day
            ? ` ${summary.today_not_called} still to call today.`
            : ' The weekend shows who was missed. Marking opens again on Monday.'}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <FilterButton active={scope === 'today'} onClick={() => setScope('today')} label="Today" />
        <FilterButton active={scope === 'week'} onClick={() => setScope('week')} label="This week" />
        <FilterButton active={status === 'not_called'} onClick={() => setStatus('not_called')} label="Not called" />
        <FilterButton active={status === 'called'} onClick={() => setStatus('called')} label="Called" />
        <FilterButton active={status === 'all'} onClick={() => setStatus('all')} label="All" />
      </div>
      {loading && <p className="text-sm text-muted-foreground">Opening the book…</p>}
      {!loading && (book?.results || []).length === 0 && (
        <p className="text-sm text-muted-foreground">No customers in this list.</p>
      )}
      <ul className="space-y-3">
        {(book?.results || []).map((row) => (
          <CallRow
            key={row.customer_id}
            row={row}
            markingOpen={markingOpen}
            saving={savingId === row.customer_id}
            onSaved={load}
            onSaving={setSavingId}
          />
        ))}
      </ul>
      {canEditPlan && plan && (
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
 * One customer row: number, last request, and the mark form.
 *
 * @param {object} props.row Book row from the API.
 * @param {boolean} props.markingOpen False on Saturday and Sunday.
 * @param {boolean} props.saving True while this row is posting.
 * @param {Function} props.onSaved Reloads the book.
 * @param {Function} props.onSaving Sets the row id currently saving.
 */
function CallRow({ row, markingOpen, saving, onSaved, onSaving }) {
  const [outcome, setOutcome] = useState(row.outcome || 'called');
  const [summary, setSummary] = useState(row.request_summary || row.previous_summary || '');
  const place = [row.ward, row.sub_county, row.county].filter(Boolean).join(', ');
  const note = row.called_this_week ? row.request_summary : row.previous_summary;

  const dial = async () => {
    try {
      await customersAPI.holdCall(row.customer_id);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not hold this customer.');
      return;
    }
    window.location.href = `tel:${row.phone}`;
  };

  const mark = async () => {
    onSaving(row.customer_id);
    try {
      await customersAPI.markCall(row.customer_id, {
        outcome,
        request_summary: summary,
      });
      toast.success(outcome === 'ask_later' ? 'Saved to ask later.' : 'Marked called this week.');
      onSaved();
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not mark this call.');
    } finally {
      onSaving(null);
    }
  };

  return (
    <li className="rounded-md border border-border p-3" data-testid={`call-row-${row.customer_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-foreground">{row.name}</p>
          <p className="text-sm text-muted-foreground">
            {place || 'No location'} · {weekdayLabel(row.weekday)}
            {row.buyer_segment === 'dormant' || row.buyer_segment === 'at_risk'
              ? ` · ${row.buyer_segment === 'dormant' ? 'Dormant' : 'Cooling off'}`
              : ''}
          </p>
        </div>
        <a className="text-sm font-medium text-primary" href={`tel:${row.phone}`}>
          {row.phone}
        </a>
      </div>
      {note && (
        <p className="mt-2 text-sm text-foreground">
          {row.called_this_week ? outcomeLabel(row.outcome) : 'Last request'}: {note}
        </p>
      )}
      {row.called_this_week && (
        <p className="mt-1 text-xs text-muted-foreground">Called this week{row.called_by ? ` by ${row.called_by}` : ''}.</p>
      )}
      {row.hold && !row.hold.held_by_me && (
        <p className="mt-1 text-xs text-muted-foreground">{row.hold.held_by} is calling them now.</p>
      )}
      {markingOpen && !row.called_this_week && (
        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
          <Button type="button" variant="outline" onClick={dial}>Call</Button>
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">Outcome</span>
            <select
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              value={outcome}
              aria-label={`Outcome for ${row.name}`}
              onChange={(event) => setOutcome(event.target.value)}
            >
              {CALL_OUTCOMES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="min-w-0 flex-1 text-sm">
            <span className="mb-1 block text-muted-foreground">Request, or ask later</span>
            <Input
              value={summary}
              maxLength={500}
              aria-label={`Request for ${row.name}`}
              onChange={(event) => setSummary(event.target.value)}
            />
          </label>
          <Button type="button" onClick={mark} disabled={saving}>
            {saving ? 'Saving…' : 'Mark called'}
          </Button>
        </div>
      )}
    </li>
  );
}

/**
 * Toggle chip for scope and status.
 *
 * @param {object} props.active Whether this chip is the current filter.
 * @param {Function} props.onClick Selects the filter.
 * @param {string} props.label Visible label, at most 20 characters.
 */
function FilterButton({ active, onClick, label }) {
  return (
    <Button type="button" variant={active ? 'default' : 'outline'} onClick={onClick}>
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
        Customers with no valid location are called on the weekday you pick. A ward row beats a sub-county row, which beats a county row. Locations with no row are spread across Monday to Friday.
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
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map((label, index) => (
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
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map((label, day) => (
              <option key={label} value={day}>{label}</option>
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
