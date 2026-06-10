import React, { useEffect, useState } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import { stripSettingLabelPrefix } from '../../utils/moduleSettingGroups';
import { PENDING_APPROVALS_NAV } from '../../utils/makerChecker';

export default function ModuleSettingChangeDialog({
  open,
  onOpenChange,
  setting,
  enabling,
  makerCheckerOn,
  userMayApprove,
  onConfirm,
  busy,
}) {
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (!open) setReason('');
  }, [open]);

  if (!setting) return null;

  const label = stripSettingLabelPrefix(setting.label);
  const action = enabling ? 'Turn on' : 'Turn off';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" description={`Confirm ${action.toLowerCase()} ${label}`}>
        <DialogHeader>
          <DialogTitle>
            {action} &ldquo;{label}&rdquo;?
          </DialogTitle>
          {setting.description ? (
            <DialogDescription className="text-left">{setting.description}</DialogDescription>
          ) : null}
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2">
            <span className="text-muted-foreground">{enabling ? 'Off' : 'On'}</span>
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="font-medium">{enabling ? 'On' : 'Off'}</span>
          </div>

          {setting.impact === 'high' ? (
            <p className="rounded-md border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-xs text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              This is a sensitive rule — it can change checkout, permissions, stock behaviour, or
              what staff see in the app.
            </p>
          ) : null}

          {makerCheckerOn ? (
            <ChangeReasonField context="settings" value={reason} onChange={setReason} />
          ) : (
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
              This saves immediately for all users on their next page load.
            </p>
          )}

          {makerCheckerOn && userMayApprove ? (
            <p className="text-xs text-muted-foreground">
              After submitting, open <strong>{PENDING_APPROVALS_NAV}</strong> to approve it yourself.
            </p>
          ) : null}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => onConfirm(reason)}
            disabled={busy || (makerCheckerOn && !reason.trim())}
          >
            {busy ? 'Saving…' : makerCheckerOn ? 'Submit for approval' : 'Apply change'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
