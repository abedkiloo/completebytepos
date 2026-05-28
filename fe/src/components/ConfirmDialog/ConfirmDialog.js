import React from 'react';
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { cn } from '../../lib/cn';

/**
 * Drop-in upgrade of the legacy ConfirmDialog.
 *
 * Public API kept identical (isOpen, title, message, onConfirm, onCancel,
 * confirmText, cancelText, type) so every existing caller — invoice delete,
 * stock-movement undo, user delete, module-settings toggle — instantly picks
 * up the new shadcn dialog + button styling and proper focus/escape handling.
 */
const ICONS_BY_TYPE = {
  danger: { Icon: AlertTriangle, tone: 'text-destructive', bg: 'bg-destructive/10' },
  warning: { Icon: AlertCircle, tone: 'text-warning', bg: 'bg-warning/10' },
  info: { Icon: Info, tone: 'text-primary', bg: 'bg-primary/10' },
};

const BUTTON_VARIANT_BY_TYPE = {
  danger: 'destructive',
  warning: 'default',
  info: 'default',
};

const ConfirmDialog = ({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  type = 'danger',
  busy = false,
}) => {
  const { Icon, tone, bg } = ICONS_BY_TYPE[type] || ICONS_BY_TYPE.danger;
  const buttonVariant = BUTTON_VARIANT_BY_TYPE[type] || 'destructive';

  return (
    <Dialog
      open={!!isOpen}
      onOpenChange={(next) => {
        if (!next && !busy) onCancel?.();
      }}
    >
      <DialogContent
        className="sm:max-w-md"
        // Fallback hidden description so the dialog is a11y-correct even
        // when the caller doesn't pass a visible ``message`` (e.g. simple
        // "Are you sure?" confirmations).
        description={message ? undefined : title || 'Please confirm this action.'}
      >
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-full', bg)}>
              <Icon className={cn('h-5 w-5', tone)} />
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <DialogTitle>{title || 'Confirm action'}</DialogTitle>
              {message && (
                <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                  {message}
                </DialogDescription>
              )}
            </div>
          </div>
        </DialogHeader>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            {cancelText}
          </Button>
          <Button variant={buttonVariant} onClick={onConfirm} disabled={busy}>
            {busy ? 'Working…' : confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ConfirmDialog;
