import React, { useEffect, useRef } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

import { cn } from '../../lib/cn';

const VARIANTS = {
  error: {
    className: 'form-banner-error border-destructive/40 bg-destructive/10 text-destructive',
    Icon: AlertCircle,
    role: 'alert',
  },
  warning: {
    className:
      'mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-950 dark:text-amber-100',
    Icon: AlertCircle,
    role: 'status',
  },
  success: {
    className:
      'mb-3 rounded-md border border-emerald-500/35 bg-emerald-500/10 px-3 py-2.5 text-sm text-emerald-900 dark:text-emerald-100',
    Icon: CheckCircle2,
    role: 'status',
  },
  info: {
    className:
      'mb-3 rounded-md border border-border bg-muted/60 px-3 py-2.5 text-sm text-foreground',
    Icon: Info,
    role: 'status',
  },
};

/**
 * Persistent message at the top of a form (in addition to corner toasts).
 * Non-technical users often miss toasts; this stays until dismissed or cleared.
 */
export default function FormBanner({
  message,
  type = 'error',
  onDismiss,
  className = '',
  autoFocus = true,
}) {
  const ref = useRef(null);
  const text = typeof message === 'string' ? message.trim() : '';
  const variant = VARIANTS[type] || VARIANTS.error;
  const Icon = variant.Icon;

  useEffect(() => {
    if (!autoFocus || !text || !ref.current) return;
    try {
      ref.current.focus({ preventScroll: false });
      ref.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch {
      /* ignore */
    }
  }, [autoFocus, text]);

  if (!text) return null;

  return (
    <div
      ref={ref}
      tabIndex={-1}
      role={variant.role}
      className={cn(
        'flex items-start gap-2 outline-none',
        variant.className,
        className
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1 font-medium leading-snug">{text}</p>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded p-0.5 opacity-70 hover:opacity-100"
          aria-label="Dismiss message"
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}
