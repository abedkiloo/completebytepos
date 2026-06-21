import React from 'react';
import { cn } from '../../lib/cn';
import { formatNavBadgeCount } from '../../utils/navBadges';

/** Small count pill for sidebar nav links. */
export default function NavCountBadge({ count, className, labelPrefix = 'pending' }) {
  const text = formatNavBadgeCount(count);
  if (!text) return null;

  return (
    <span
      className={cn(
        'ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full',
        'bg-destructive px-1.5 text-[10px] font-bold leading-none text-destructive-foreground',
        className
      )}
      aria-label={`${count} ${labelPrefix}`}
    >
      {text}
    </span>
  );
}
