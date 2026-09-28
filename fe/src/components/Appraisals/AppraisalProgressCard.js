import React from 'react';
import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';

import { cn } from '../../lib/cn';
import { Card, CardContent } from '../ui/card';
import { appraisalTone, kes, starGlyphs } from '../../utils/appraisalStars';
import AppraisalProgressBar from './AppraisalProgressBar';

function StarPill({ stars, tone, label }) {
  const theme = appraisalTone(tone);
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', theme.pill)}>
      <span aria-hidden>{starGlyphs(stars)}</span>
      <span>{Number(stars).toFixed(Number(stars) % 1 ? 1 : 0)}★</span>
      {label ? <span className="font-medium opacity-90">{label}</span> : null}
    </span>
  );
}

export default function AppraisalProgressCard({
  snapshot,
  compact = false,
  className,
}) {
  if (!snapshot) return null;
  const { today, month, year, greeting, staff } = snapshot;
  const tone = today?.tone || month?.tone || 'rose';
  const theme = appraisalTone(tone);

  return (
    <Card
      className={cn('overflow-hidden border', theme.border, theme.bg, className)}
      data-testid="appraisal-progress-card"
    >
      <CardContent className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Star className="h-3.5 w-3.5" />
              {staff?.name ? `${staff.name} · 5-star progress` : '5-star progress'}
            </p>
            <h2 className={cn('mt-1 text-lg font-semibold leading-tight', theme.text)}>
              {greeting?.headline || 'Keep pushing to the next star'}
            </h2>
            {!compact && greeting?.detail ? (
              <p className="mt-1 text-sm text-muted-foreground">{greeting.detail}</p>
            ) : null}
          </div>
          <StarPill stars={today?.stars} tone={today?.tone} label={today?.label} />
        </div>

        <AppraisalProgressBar
          progress={today?.target_progress}
          tone={today?.tone}
          label={`Today ${kes(today?.sales)} / daily target ${kes(today?.target)}`}
        />
        <AppraisalProgressBar
          progress={month?.progress_to_four_star}
          tone={month?.four_star_month ? 'emerald' : month?.tone}
          label={`Month avg ${Number(month?.official_average || 0).toFixed(2)}/5 · bonus ${kes(month?.bonus)}`}
        />
        <AppraisalProgressBar
          progress={year?.progress_to_increment}
          tone={year?.qualifies ? 'gold' : year?.tone}
          label={`Year ${year?.four_star_months || 0}/${year?.four_star_months_required || 8} four-star months`}
        />

        {!compact && (
          <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
            <p>
              Next daily star: {today?.next_min != null ? kes(today.amount_to_next) : 'Max'}
            </p>
            <p>
              Next bonus band: {month?.next_bonus_min != null ? kes(month.amount_to_next_bonus) : 'Max'}
            </p>
            <p>
              Year-end basic: {kes(year?.new_basic)} {year?.qualifies ? '(on track)' : '(not yet)'}
            </p>
          </div>
        )}

        {compact ? (
          <Link to="/appraisals" className="text-sm font-medium underline underline-offset-2">
            Open full appraisal
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
