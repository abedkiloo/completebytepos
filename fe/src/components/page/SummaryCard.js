import React from 'react';
import { cn } from '../../lib/cn';
import { Card, CardContent } from '../ui/card';

const TONE_STYLES = {
  default: 'bg-primary/10 text-primary',
  warning: 'bg-warning/15 text-warning',
  destructive: 'bg-destructive/10 text-destructive',
  success: 'bg-success/15 text-success',
};

export function SummaryCard({ icon: Icon, label, value, tone = 'default', className }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="flex items-center gap-3 p-3">
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
        </div>
      </CardContent>
    </Card>
  );
}
