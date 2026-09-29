import React from 'react';
import { Star } from 'lucide-react';

import { cn } from '../../lib/cn';

export default function AppraisalDailyTips({ pack, compact = false, emphasis = false }) {
  const tips = Array.isArray(pack?.tips) ? pack.tips.filter(Boolean).slice(0, 5) : [];
  if (!tips.length) return null;

  if (compact) {
    return (
      <p
        className={cn(
          'text-sm leading-snug',
          emphasis ? 'text-white/85' : 'text-muted-foreground',
        )}
        data-testid="appraisal-today-move"
      >
        <span className={cn('font-semibold', emphasis ? 'text-white' : 'text-foreground')}>
          Today’s move:{' '}
        </span>
        {tips[0]}
      </p>
    );
  }

  return (
    <section
      className={cn(
        'rounded-lg border p-3 sm:p-4',
        emphasis ? 'border-white/20 bg-black/25' : 'border-border bg-background/60',
      )}
      data-testid="appraisal-daily-tips"
    >
      <p
        className={cn(
          'flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-[0.14em]',
          emphasis ? 'text-white/70' : 'text-muted-foreground',
        )}
      >
        <Star className="h-3.5 w-3.5" />
        How to hit today’s target
      </p>
      <h3 className={cn('mt-1.5 text-sm font-bold', emphasis ? 'text-white' : 'text-foreground')}>
        {pack.title}
      </h3>
      {pack.why ? (
        <p className={cn('mt-1 text-xs leading-relaxed', emphasis ? 'text-white/70' : 'text-muted-foreground')}>
          {pack.why}
        </p>
      ) : null}
      <ol className="mt-3 space-y-2">
        {tips.map((tip, index) => (
          <li key={`${index}-${tip.slice(0, 24)}`} className="flex gap-2.5 text-sm leading-snug">
            <span
              className={cn(
                'mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold',
                emphasis ? 'bg-amber-400 text-slate-950' : 'bg-amber-100 text-amber-950',
              )}
            >
              {index + 1}
            </span>
            <span className={emphasis ? 'text-white/90' : 'text-foreground'}>{tip}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
