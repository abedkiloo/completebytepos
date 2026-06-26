import React from 'react';
import { Info } from 'lucide-react';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { makerCheckerReasonCopy } from '../../utils/makerChecker';

export default function ChangeReasonField({
  value,
  onChange,
  required = true,
  context = 'default',
  hint,
  label,
  placeholder,
  error,
  requiresApproval = true,
}) {
  const copy = makerCheckerReasonCopy(context);
  const resolvedLabel = label ?? copy.label;
  const resolvedPlaceholder = placeholder ?? copy.placeholder;
  const resolvedHint = hint ?? copy.summary;

  return (
    <div
      className={
        requiresApproval
          ? 'form-group space-y-2 rounded-md border border-amber-200 bg-amber-50/80 p-3 dark:border-amber-900 dark:bg-amber-950/30'
          : 'form-group space-y-2'
      }
    >
      {requiresApproval ? (
        <div className="flex gap-2 text-sm text-amber-950 dark:text-amber-100">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
          <div className="space-y-1.5">
            <p>
              <span className="font-medium">Manager approval required.</span>{' '}
              {resolvedHint}
            </p>
            {copy.approverHint ? (
              <p className="text-xs text-amber-800 dark:text-amber-200">{copy.approverHint}</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                A manager or admin will review your request in the approval queue.
              </p>
            )}
          </div>
        </div>
      ) : resolvedHint ? (
        <p className="text-xs text-muted-foreground">{resolvedHint}</p>
      ) : null}
      <div>
        <Label htmlFor="change_reason" className="text-sm font-medium">
          {resolvedLabel} {required ? '*' : ''}
        </Label>
        <Input
          id="change_reason"
          name="change_reason"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={resolvedPlaceholder}
          className="mt-1.5"
          required={required}
          aria-invalid={Boolean(error)}
        />
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
      </div>
    </div>
  );
}
