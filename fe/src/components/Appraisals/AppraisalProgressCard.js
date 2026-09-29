import React from 'react';
import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';

import { cn } from '../../lib/cn';
import { Card, CardContent } from '../ui/card';
import { appraisalTone, kes, starGlyphs } from '../../utils/appraisalStars';
import AppraisalProgressBar from './AppraisalProgressBar';
import AppraisalDailyTips from './AppraisalDailyTips';

function StarPill({ stars, tone, label, emphasis }) {
  const theme = appraisalTone(tone);
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold shadow-sm',
        theme.pill,
        emphasis && 'text-sm',
      )}
    >
      <span aria-hidden className={emphasis ? 'text-base' : undefined}>
        {starGlyphs(stars)}
      </span>
      <span>{Number(stars).toFixed(Number(stars) % 1 ? 1 : 0)}★</span>
      {label ? <span className="font-medium opacity-90">{label}</span> : null}
    </span>
  );
}

export default function AppraisalProgressCard({
  snapshot,
  compact = false,
  emphasis = false,
  actions,
  className,
}) {
  if (!snapshot) return null;
  const { today, month, year, greeting, staff, today_tips: todayTips } = snapshot;
  const tone = today?.tone || month?.tone || 'rose';
  const theme = appraisalTone(tone);
  const toTarget = Number(today?.amount_to_target || 0);

  return (
    <Card
      className={cn(
        'overflow-hidden border',
        emphasis
          ? cn(
              'border-2 text-white shadow-[0_24px_60px_rgba(0,0,0,0.55)]',
              theme.emphasisPanel,
              theme.emphasisBorder,
            )
          : cn(theme.border, theme.bg),
        className,
      )}
      data-testid="appraisal-progress-card"
    >
      <CardContent className={cn('space-y-4', emphasis ? 'p-5 sm:p-6' : 'p-4')}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p
              className={cn(
                'flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-[0.16em]',
                emphasis ? 'text-white/70' : 'text-muted-foreground',
              )}
            >
              <Star className="h-3.5 w-3.5" />
              {staff?.name ? `${staff.name} · your progress` : 'Your progress'}
            </p>
            <h2
              id={emphasis ? 'appraisal-greeting-title' : undefined}
              className={cn(
                'mt-1.5 font-extrabold leading-tight',
                emphasis ? 'text-2xl text-white' : cn('text-lg', theme.text),
              )}
            >
              {greeting?.headline || 'Keep pushing to the next star'}
            </h2>
            {!compact && greeting?.detail ? (
              <p className={cn('mt-1.5 text-sm', emphasis ? 'text-white/80' : 'text-muted-foreground')}>
                {greeting.detail}
              </p>
            ) : null}
          </div>
          <StarPill stars={today?.stars} tone={today?.tone} label={today?.label} emphasis={emphasis} />
        </div>

        <AppraisalProgressBar
          progress={today?.target_progress}
          tone={today?.tone}
          emphasis={emphasis}
          label={`Today ${kes(today?.sales)} of ${kes(today?.target)} daily target`}
        />
        <AppraisalProgressBar
          progress={month?.progress_to_four_star}
          tone={month?.four_star_month ? 'emerald' : month?.tone}
          emphasis={emphasis}
          label={`This month ${Number(month?.official_average || 0).toFixed(2)}/5 toward a 4-star month`}
        />
        <AppraisalProgressBar
          progress={year?.progress_to_increment}
          tone={year?.qualifies ? 'gold' : year?.tone}
          emphasis={emphasis}
          label={`Year ${year?.four_star_months || 0}/${year?.four_star_months_required || 8} four-star months`}
        />

        <AppraisalDailyTips pack={todayTips} compact={compact} emphasis={emphasis} />

        {!compact && (
          <div
            className={cn(
              'grid gap-2 text-xs sm:grid-cols-2',
              emphasis ? 'text-white/70' : 'text-muted-foreground',
            )}
          >
            <p>
              {toTarget > 0
                ? `Still needed today: ${kes(toTarget)}`
                : 'Daily target met'}
            </p>
            <p>
              Year-end increment: {kes(year?.new_basic)} {year?.qualifies ? '(on track)' : '(not yet)'}
            </p>
          </div>
        )}

        {compact ? (
          <Link
            to="/appraisals"
            className={cn(
              'text-sm font-semibold underline underline-offset-2',
              emphasis ? 'text-white' : undefined,
            )}
          >
            Open my progress
          </Link>
        ) : null}

        {actions ? <div className="flex flex-wrap justify-end gap-2 pt-1">{actions}</div> : null}
      </CardContent>
    </Card>
  );
}
