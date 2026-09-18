import React from 'react';
import { cn } from '../../lib/cn';
import { Card, CardContent } from '../ui/card';

const TONE_STYLES = {
  default: 'bg-primary/10 text-primary',
  warning: 'bg-warning/15 text-warning',
  destructive: 'bg-destructive/10 text-destructive',
  success: 'bg-success/15 text-success',
};

export function SummaryCard({
  icon: Icon,
  label,
  value,
  subtext,
  tone = 'default',
  className,
  onClick,
}) {
  const clickable = typeof onClick === 'function';
  const inner = (
    <>
      {Icon && (
        <div
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
            TONE_STYLES[tone] || TONE_STYLES.default
          )}
        >
          <Icon className="h-5 w-5" aria-hidden />
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="truncate text-lg font-bold tabular-nums text-foreground">{value}</p>
        {subtext ? (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtext}</p>
        ) : null}
      </div>
    </>
  );

  return (
    <Card
      className={cn(
        'overflow-hidden',
        clickable && 'transition-colors hover:border-primary/40 hover:bg-muted/30',
        className
      )}
    >
      {clickable ? (
        <button
          type="button"
          onClick={onClick}
          className="flex w-full items-center gap-3 p-3 text-left"
        >
          {inner}
        </button>
      ) : (
        <CardContent className="flex items-center gap-3 p-3">{inner}</CardContent>
      )}
    </Card>
  );
}
