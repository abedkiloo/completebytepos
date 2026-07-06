import React from 'react';
import { cn } from '../../lib/cn';
import { REPORT_PERIODS } from '../../utils/reportPeriods';

export default function PeriodPills({ value, onChange, className, size = 'sm' }) {
  return (
    <div
      className={cn(
        'inline-flex flex-wrap items-center rounded-lg border bg-muted/30 p-0.5',
        size === 'default' ? 'text-sm' : 'text-xs',
        className
      )}
      role="tablist"
      aria-label="Report period"
    >
      {REPORT_PERIODS.map((period) => (
        <button
          key={period.id}
          type="button"
          role="tab"
          aria-selected={value === period.id}
          onClick={() => onChange(period.id)}
          className={cn(
            'rounded-md font-medium transition',
            size === 'default' ? 'px-3 py-1.5' : 'px-2.5 py-1',
            value === period.id
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}
