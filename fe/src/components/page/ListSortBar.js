import React from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { cn } from '../../lib/cn';
import { LIST_RANK_OPTIONS, toggleListOrdering } from '../../utils/listOrdering';

export function ListSortBar({
  value = '',
  onChange,
  options = LIST_RANK_OPTIONS,
  className,
}) {
  if (!onChange) return null;
  return (
    <label className={cn('inline-flex min-w-[11rem] items-center gap-2 text-sm', className)}>
      <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">Rank by</span>
      <select
        data-testid="list-rank-by"
        aria-label="Rank by"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
      >
        {options.map((opt) => (
          <option key={opt.value || 'default'} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SortableHeadButton({
  sortKey,
  ordering,
  onOrderingChange,
  children,
  className,
}) {
  if (!sortKey || !onOrderingChange) {
    return children;
  }
  const active = ordering === sortKey || ordering === `-${sortKey}`;
  const descending = ordering === `-${sortKey}`;
  const Icon = !active ? ArrowUpDown : descending ? ArrowDown : ArrowUp;
  return (
    <button
      type="button"
      data-testid={`sort-${sortKey}`}
      aria-label={`Rank by ${typeof children === 'string' ? children : sortKey}`}
      onClick={() => onOrderingChange(toggleListOrdering(ordering, sortKey))}
      className={cn(
        'inline-flex items-center gap-1 font-medium hover:text-foreground',
        active ? 'text-foreground' : 'text-muted-foreground',
        className
      )}
    >
      {children}
      <Icon className="h-3.5 w-3.5" aria-hidden />
    </button>
  );
}
