import React from 'react';
import { cn } from '../../lib/cn';
import { appraisalTone, percentLabel } from '../../utils/appraisalStars';

export default function AppraisalProgressBar({
  progress = 0,
  tone = 'rose',
  label,
  className,
}) {
  const theme = appraisalTone(tone);
  const width = Math.max(0, Math.min(100, Math.round((Number(progress) || 0) * 100)));
  return (
    <div className={cn('space-y-1', className)}>
      {label ? (
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className={cn('font-medium', theme.text)}>{label}</span>
          <span className="tabular-nums text-muted-foreground">{percentLabel(progress)}</span>
        </div>
      ) : null}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r transition-all duration-500', theme.bar)}
          style={{ width: `${width}%` }}
          role="progressbar"
          aria-valuenow={width}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
