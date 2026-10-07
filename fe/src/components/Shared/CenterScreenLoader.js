import React from 'react';
import { createPortal } from 'react-dom';
import { Loader2 } from 'lucide-react';

/**
 * Full-viewport centered loader for longer in-flight actions.
 * Reuse anywhere a mutation/export blocks the UI; leave PageLoading
 * skeletons and specialized waits (e.g. STK) alone.
 */
export default function CenterScreenLoader({
  open = false,
  label = 'Loading…',
  testId = 'center-screen-loader',
}) {
  if (!open || typeof document === 'undefined') return null;

  return createPortal(
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={testId}
      className="fixed inset-0 z-[4000] flex items-center justify-center bg-black/40 p-4 backdrop-blur-[1px]"
    >
      <div className="flex min-w-[12rem] flex-col items-center gap-3 rounded-lg border bg-background px-6 py-5 shadow-lg">
        <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
        <p className="text-center text-sm font-medium text-foreground">{label}</p>
      </div>
    </div>,
    document.body
  );
}
