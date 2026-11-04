/**
 * Priority levels for daily notes and tasks — icons + colours for the desk UI.
 */

import { AlertTriangle, ArrowDown, CircleDot } from 'lucide-react';

export const PRIORITY_HIGH = 'high';
export const PRIORITY_MEDIUM = 'medium';
export const PRIORITY_LOW = 'low';

export const DAILY_NOTE_PRIORITIES = [
  {
    id: PRIORITY_HIGH,
    label: 'Highest',
    description: 'Do first — urgent or blocking',
    Icon: AlertTriangle,
    // Distinct red / rose
    className: 'border-rose-600/40 bg-rose-500/15 text-rose-800 dark:text-rose-200',
    barClassName: 'bg-rose-500',
    chipClassName: 'text-rose-700 dark:text-rose-300',
  },
  {
    id: PRIORITY_MEDIUM,
    label: 'Medium',
    description: 'Normal follow-up today',
    Icon: CircleDot,
    // Distinct amber
    className: 'border-amber-600/40 bg-amber-500/15 text-amber-900 dark:text-amber-100',
    barClassName: 'bg-amber-500',
    chipClassName: 'text-amber-800 dark:text-amber-200',
  },
  {
    id: PRIORITY_LOW,
    label: 'Less',
    description: 'Nice to have / can wait',
    Icon: ArrowDown,
    // Distinct slate / blue-grey
    className: 'border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-200',
    barClassName: 'bg-slate-500',
    chipClassName: 'text-slate-600 dark:text-slate-300',
  },
];

const BY_ID = Object.fromEntries(DAILY_NOTE_PRIORITIES.map((p) => [p.id, p]));

export function normalizePriority(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === PRIORITY_HIGH || raw === PRIORITY_MEDIUM || raw === PRIORITY_LOW) {
    return raw;
  }
  return PRIORITY_MEDIUM;
}

export function priorityMeta(value) {
  return BY_ID[normalizePriority(value)] || BY_ID[PRIORITY_MEDIUM];
}

export function prioritySortRank(value) {
  const id = normalizePriority(value);
  if (id === PRIORITY_HIGH) return 0;
  if (id === PRIORITY_LOW) return 2;
  return 1;
}

export function sortByPriorityThen(a, b, nextCompare) {
  const diff = prioritySortRank(a?.priority) - prioritySortRank(b?.priority);
  if (diff !== 0) return diff;
  return typeof nextCompare === 'function' ? nextCompare(a, b) : 0;
}
