import React from 'react';
import { cn } from '../../lib/cn';
import { priorityMeta } from '../../utils/dailyNotesPriority';

/**
 * Compact priority chip with distinct icon + colour per level.
 */
export default function PriorityBadge({ priority, className, showLabel = true }) {
  const meta = priorityMeta(priority);
  const Icon = meta.Icon;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold',
        meta.className,
        className,
      )}
      data-testid={`priority-badge-${meta.id}`}
      title={meta.description}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden />
      {showLabel ? meta.label : null}
    </span>
  );
}
