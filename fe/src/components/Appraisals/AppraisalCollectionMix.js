import React from 'react';

import { cn } from '../../lib/cn';
import { kes } from '../../utils/appraisalStars';

/** Paid (green) vs still-on-credit (rose) share of goods sold. */
export function collectionMixFromAmounts({ sold = 0, collected = 0 } = {}) {
  const total = Math.max(0, Number(sold) || 0);
  const paid = Math.max(0, Math.min(total, Number(collected) || 0));
  const debt = Math.max(0, total - paid);
  if (total <= 0) {
    return { total: 0, paid: 0, debt: 0, paidPct: 0, debtPct: 0, uncollectedPct: 0 };
  }
  const paidPct = Math.min(100, (paid / total) * 100);
  const debtPct = Math.min(100 - paidPct, (debt / total) * 100);
  return {
    total,
    paid,
    debt,
    paidPct,
    debtPct,
    uncollectedPct: debtPct,
  };
}

export default function AppraisalCollectionMix({
  sold,
  collected,
  requiredRatio = 0.8,
  className,
  emphasis = false,
  showLegend = true,
  label = 'Collected vs still on credit',
}) {
  const mix = collectionMixFromAmounts({ sold, collected });
  const needPct = Math.round(Number(requiredRatio || 0.8) * 100);
  const havePct = Math.round(mix.paidPct);
  return (
    <div
      className={cn('space-y-1.5', className)}
      data-testid="appraisal-collection-mix"
    >
      {label ? (
        <div className="flex items-center justify-between gap-2 text-xs">
          <span
            className={cn(
              'font-semibold',
              emphasis ? 'text-white/90' : 'text-foreground',
            )}
          >
            {label}
          </span>
          <span
            className={cn(
              'tabular-nums',
              emphasis ? 'text-white/60' : 'text-muted-foreground',
            )}
          >
            {havePct}% collected · need {needPct}%
          </span>
        </div>
      ) : null}
      <div
        className={cn(
          'flex w-full overflow-hidden rounded-full',
          emphasis ? 'h-3.5 bg-white/15' : 'h-2.5 bg-muted',
        )}
        role="img"
        aria-label={`Collected ${havePct} percent, on credit ${Math.round(mix.debtPct)} percent`}
      >
        {mix.paidPct > 0 ? (
          <div
            className="h-full bg-emerald-500 transition-[width]"
            style={{ width: `${mix.paidPct}%` }}
            data-testid="appraisal-collected-segment"
          />
        ) : null}
        {mix.debtPct > 0 ? (
          <div
            className="h-full bg-rose-500 transition-[width]"
            style={{ width: `${mix.debtPct}%` }}
            data-testid="appraisal-debt-segment"
          />
        ) : null}
      </div>
      {showLegend ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 font-medium',
              emphasis ? 'text-emerald-200' : 'text-emerald-700 dark:text-emerald-400',
            )}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden />
            Collected {kes(mix.paid)}
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1.5 font-medium',
              emphasis ? 'text-rose-200' : 'text-rose-700 dark:text-rose-400',
            )}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-rose-500" aria-hidden />
            On credit {kes(mix.debt)}
            {mix.uncollectedPct > 0
              ? ` (${Math.round(mix.uncollectedPct)}% of sales)`
              : ''}
          </span>
        </div>
      ) : null}
    </div>
  );
}
