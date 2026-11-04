import React from 'react';
import { cn } from '../../lib/cn';
import {
  DAILY_NOTE_PRIORITIES,
  normalizePriority,
} from '../../utils/dailyNotesPriority';

/**
 * Segmented priority control for note/task create and edit forms.
 */
export default function PriorityPicker({
  value,
  onChange,
  name = 'priority',
  disabled = false,
}) {
  const current = normalizePriority(value);

  return (
    <div className="form-group" data-testid="priority-picker">
      <label htmlFor={`${name}-group`}>Priority</label>
      <div
        id={`${name}-group`}
        role="radiogroup"
        aria-label="Priority"
        className="grid grid-cols-3 gap-2"
      >
        {DAILY_NOTE_PRIORITIES.map((level) => {
          const selected = current === level.id;
          const Icon = level.Icon;
          return (
            <button
              key={level.id}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              data-testid={`priority-option-${level.id}`}
              onClick={() => onChange(level.id)}
              className={cn(
                'flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-center transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                selected
                  ? cn(level.className, 'ring-1 ring-offset-1 ring-offset-background')
                  : 'border-border bg-background text-muted-foreground hover:bg-muted/50',
              )}
            >
              <Icon className="h-4 w-4" aria-hidden />
              <span className="text-xs font-semibold">{level.label}</span>
            </button>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {DAILY_NOTE_PRIORITIES.find((p) => p.id === current)?.description}
      </p>
    </div>
  );
}
