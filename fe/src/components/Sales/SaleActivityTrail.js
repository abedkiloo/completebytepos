import React from 'react';
import { Check, History, RotateCcw, Undo2, User, X } from 'lucide-react';
import { formatDateTime } from '../../utils/formatters';
import { cn } from '../../lib/cn';

const KIND_STYLES = {
  recorded: 'bg-slate-100 text-slate-700',
  served_by: 'bg-slate-100 text-slate-700',
  submitted: 'bg-sky-100 text-sky-800',
  pending: 'bg-amber-100 text-amber-900',
  approved: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-rose-100 text-rose-800',
  void: 'bg-amber-100 text-amber-900',
  rollback: 'bg-violet-100 text-violet-900',
  cancelled: 'bg-rose-100 text-rose-800',
  date_corrected: 'bg-slate-100 text-slate-700',
};

function KindIcon({ kind }) {
  if (kind === 'approved') return <Check className="h-3.5 w-3.5" aria-hidden />;
  if (kind === 'rejected' || kind === 'cancelled') return <X className="h-3.5 w-3.5" aria-hidden />;
  if (kind === 'rollback') return <Undo2 className="h-3.5 w-3.5" aria-hidden />;
  if (kind === 'void') return <RotateCcw className="h-3.5 w-3.5" aria-hidden />;
  if (kind === 'recorded' || kind === 'served_by') return <User className="h-3.5 w-3.5" aria-hidden />;
  return <History className="h-3.5 w-3.5" aria-hidden />;
}

/**
 * Accountability trail for a sale — who recorded, approved, voided, cancelled, etc.
 */
export default function SaleActivityTrail({ activity = [], className }) {
  const rows = Array.isArray(activity) ? activity.filter(Boolean) : [];
  if (!rows.length) return null;

  return (
    <div
      className={cn('space-y-2 rounded-md border bg-muted/20 px-3 py-2 text-sm', className)}
      data-testid="sale-activity-trail"
    >
      <div className="flex items-center gap-1.5">
        <History className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Activity
        </p>
      </div>
      <ol className="space-y-2">
        {rows.map((event) => {
          const tone = KIND_STYLES[event.kind] || KIND_STYLES.recorded;
          return (
            <li
              key={event.id || `${event.kind}-${event.at}-${event.label}`}
              className="flex gap-2"
              data-testid="sale-activity-event"
            >
              <span
                className={cn(
                  'mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                  tone,
                )}
              >
                <KindIcon kind={event.kind} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium leading-snug">{event.label}</p>
                <p className="text-xs text-muted-foreground">
                  {event.actor
                    ? `${event.actor_role ? `${event.actor_role}: ` : ''}${event.actor}`
                    : event.actor_role || 'System'}
                  {event.at ? ` · ${formatDateTime(event.at)}` : null}
                </p>
                {event.comment ? (
                  <p className="mt-0.5 text-xs text-foreground/80">
                    <span className="font-medium">Comment: </span>
                    {event.comment}
                  </p>
                ) : null}
                {event.detail ? (
                  <p className="text-xs text-muted-foreground">{event.detail}</p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
