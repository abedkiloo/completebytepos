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
    />
  );
}
