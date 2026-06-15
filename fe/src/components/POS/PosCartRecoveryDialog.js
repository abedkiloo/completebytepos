import React from 'react';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { buildCartRecoveryMessage } from '../../utils/posCartRecovery';

/**
 * Ask the cashier to resume a saved cart or start fresh (all POS variants).
 */
export default function PosCartRecoveryDialog({
  open,
  source,
  itemCount,
  label,
  previewLines = [],
  onContinue,
  onStartNew,
  busy = false,
}) {
  if (!open || !itemCount) return null;

  return (
    <ConfirmDialog
      isOpen={open}
      type="info"
      title="Resume previous sale?"
      message={buildCartRecoveryMessage({ source, itemCount, label })}
      confirmText="Continue sale"
      cancelText="Start new sale"
      onConfirm={onContinue}
      onCancel={onStartNew}
      busy={busy}
    >
      {previewLines.length > 0 && (
        <ul className="max-h-36 overflow-y-auto rounded-md border bg-muted/40 px-3 py-2 text-sm">
          {previewLines.map((line, index) => (
            <li
              key={`${line.name}-${index}`}
              className="flex justify-between gap-2 border-b border-border/60 py-1 last:border-0"
            >
              <span className="truncate text-foreground">{line.name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">×{line.quantity}</span>
            </li>
          ))}
        </ul>
      )}
    </ConfirmDialog>
  );
}
