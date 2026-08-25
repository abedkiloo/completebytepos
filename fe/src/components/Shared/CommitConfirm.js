import React from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { cn } from '../../lib/cn';
import { buildCommitRows } from '../../utils/commitConfirm';

const TONE_CLASS = {
  default: '',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-destructive',
};

const ICONS = {
  info: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertTriangle,
};

/**
 * Shared “are you sure?” dialog with a summary table before committing.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {(open: boolean) => void} props.onOpenChange
 * @param {string} props.title
 * @param {string} [props.description]
 * @param {Array<{label: string, value: string, tone?: string, emphasis?: boolean}>} props.rows
 * @param {() => void} props.onConfirm
 * @param {boolean} [props.submitting]
 * @param {string} [props.confirmText]
 * @param {string} [props.cancelText]
 * @param {'info'|'warning'|'danger'} [props.variant]
 */
export function CommitConfirm({
  open,
  onOpenChange,
  title,
  description = 'Review the summary, then confirm. This saves the change to the system.',
  rows = [],
  onConfirm,
  submitting = false,
  confirmText = 'Confirm & save',
  cancelText = 'Cancel',
  variant = 'info',
}) {
  const summaryRows = buildCommitRows(rows);
  const Icon = ICONS[variant] || ICONS.info;
  const iconTone =
    variant === 'danger'
      ? 'text-destructive'
      : variant === 'warning'
        ? 'text-warning'
        : 'text-primary';

  return (
    <Dialog
      open={!!open}
      onOpenChange={(next) => {
        if (!next && !submitting) onOpenChange?.(false);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className={cn('h-5 w-5', iconTone)} />
            {title || 'Confirm action?'}
          </DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>

        {summaryRows.length > 0 ? (
          <dl className="grid grid-cols-2 gap-y-2 rounded-md border bg-muted/40 px-4 py-3 text-sm">
            {summaryRows.map((row) => (
              <React.Fragment key={`${row.label}-${row.value}`}>
                <dt
                  className={cn(
                    'text-muted-foreground',
                    row.emphasis && 'font-medium text-foreground'
                  )}
                >
                  {row.label}
                </dt>
                <dd
                  className={cn(
                    'text-right tabular-nums',
                    row.emphasis && 'text-base font-semibold',
                    TONE_CLASS[row.tone] || ''
                  )}
                >
                  {row.value}
                </dd>
              </React.Fragment>
            ))}
          </dl>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange?.(false)} disabled={submitting}>
            {cancelText}
          </Button>
          <Button
            variant={variant === 'danger' ? 'destructive' : 'default'}
            onClick={onConfirm}
            disabled={submitting}
          >
            {submitting ? 'Saving…' : confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default CommitConfirm;
