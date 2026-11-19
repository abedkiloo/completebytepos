import React, { useCallback, useEffect, useState } from 'react';

import { leaveAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { isModuleFeatureEnabled } from '../../utils/moduleFeatures';

const KINDS = [
  { id: 'leave', label: 'Day off' },
  { id: 'sick', label: 'Sick day' },
];

function todayKey() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Ask for one day off or one sick day, and decide the requests you are allowed to see.
 *
 * A manager decides for staff. A director decides for a manager. The shop texts
 * the result to the employee and the directors.
 *
 * @returns {JSX.Element}
 */
export default function LeavePage() {
  const enabled = isModuleFeatureEnabled('employees', 'leave_requests');
  const [rows, setRows] = useState([]);
  const [allowance, setAllowance] = useState(null);
  const [canConfigure, setCanConfigure] = useState(false);
  const [shopDays, setShopDays] = useState('1');
  const [people, setPeople] = useState([]);
  const [personId, setPersonId] = useState('');
  const [personDays, setPersonDays] = useState('');
  const [kind, setKind] = useState('leave');
  const [day, setDay] = useState(todayKey);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const response = await leaveAPI.list();
    const data = response.data || {};
    setRows(data.results || []);
    setAllowance(data.allowance || null);
    setCanConfigure(Boolean(data.can_configure));
    if (data.can_configure) {
      const config = await leaveAPI.allowance();
      setShopDays(String(config.data?.shop_days ?? 1));
      setPeople(config.data?.people || []);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    load()
      .catch(() => {
        if (!cancelled) toast.error('Leave could not be loaded.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, load]);

  const submit = async (event) => {
    event.preventDefault();
    try {
      await leaveAPI.create({ kind, day, note: note.trim() });
      setNote('');
      toast.success('Request sent.');
      await load();
    } catch (error) {
      const data = error.response?.data || {};
      const message = data.day || data.kind || data.note || data.detail || 'The request was not saved.';
      toast.error(Array.isArray(message) ? message[0] : message);
    }
  };

  const decide = async (row, decision) => {
    try {
      await leaveAPI.decide(row.id, { decision });
      toast.success(decision === 'approved' ? 'Approved. The employee and directors are told.' : 'Rejected. The employee and directors are told.');
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'That decision was not saved.');
    }
  };

  if (!enabled) {
    return <p>Leave requests are switched off for this shop.</p>;
  }

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-xl font-semibold">Leave</h1>
      <p className="text-sm text-muted-foreground">
        One day at a time. A manager decides for staff. A director decides when a manager asks to be off.
        The result is sent to the employee and the directors.
      </p>
      {allowance ? (
        <p data-testid="leave-allowance">
          {allowance.remaining} of {allowance.limit} day off left in {allowance.month}.
          Sick days are not counted.
        </p>
      ) : null}
      {canConfigure ? (
        <form
          className="flex flex-wrap items-end gap-3 rounded border p-3"
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              await leaveAPI.saveAllowance({ monthly_leave_days: Number(shopDays) });
              toast.success('The shop number was saved.');
              await load();
            } catch (error) {
              toast.error(error.response?.data?.monthly_leave_days || 'That number was not saved.');
            }
          }}
        >
          <label className="text-sm">
            Days off each month for everyone
            <input
              aria-label="Days off each month for everyone"
              type="number"
              min="0"
              max="31"
              className="mt-1 block rounded border px-2 py-1"
              value={shopDays}
              onChange={(event) => setShopDays(event.target.value)}
            />
          </label>
          <button type="submit">Save for everyone</button>
          <label className="text-sm">
            One person
            <select
              aria-label="One person"
              className="mt-1 block rounded border px-2 py-1"
              value={personId}
              onChange={(event) => setPersonId(event.target.value)}
            >
              <option value="">Choose</option>
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name} ({person.effective})
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Their days
            <input
              aria-label="Their days"
              type="number"
              min="0"
              max="31"
              className="mt-1 block rounded border px-2 py-1"
              value={personDays}
              onChange={(event) => setPersonDays(event.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={async () => {
              if (!personId) return;
              try {
                await leaveAPI.saveAllowance({
                  user_id: Number(personId),
                  monthly_leave_days: personDays === '' ? null : Number(personDays),
                });
                toast.success('That person’s number was saved.');
                await load();
              } catch (error) {
                toast.error('That person’s number was not saved.');
              }
            }}
          >
            Save for this person
          </button>
        </form>
      ) : null}
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Type
          <select
            aria-label="Type"
            className="mt-1 block rounded border px-2 py-1"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            {KINDS.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Day
          <input
            aria-label="Day"
            type="date"
            className="mt-1 block rounded border px-2 py-1"
            value={day}
            onChange={(event) => setDay(event.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          Note
          <input
            aria-label="Note"
            className="mt-1 block rounded border px-2 py-1"
            value={note}
            maxLength={300}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <button type="submit" className="btn btn-primary">Send request</button>
      </form>
      {loading ? <p>Loading leave…</p> : null}
      <ul className="space-y-2">
        {rows.map((row) => (
          <li key={row.id} data-testid="leave-row" className="rounded border p-3">
            <p>
              {row.requester_name} · {row.kind === 'sick' ? 'Sick day' : 'Day off'} · {row.day} · {row.status}
            </p>
            {row.note ? <p className="text-sm">{row.note}</p> : null}
            {row.can_decide ? (
              <div className="mt-2 flex gap-2">
                <button type="button" onClick={() => decide(row, 'approved')}>Approve</button>
                <button type="button" onClick={() => decide(row, 'rejected')}>Reject</button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
