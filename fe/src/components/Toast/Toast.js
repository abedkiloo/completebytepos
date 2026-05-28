import React, { useEffect } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '../../lib/cn';

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const STYLES = {
  success: 'border-success/30 bg-success/10 text-foreground',
  error: 'border-destructive/30 bg-destructive/10 text-foreground',
  warning: 'border-warning/30 bg-warning/10 text-foreground',
  info: 'border-primary/30 bg-primary/5 text-foreground',
};

const Toast = ({ message, type = 'success', onClose, duration = 3000 }) => {
  const Icon = ICONS[type] || Info;
  const effectiveDuration = type === 'error' ? Math.max(duration, 5000) : duration;

  useEffect(() => {
    if (effectiveDuration > 0) {
      const timer = setTimeout(onClose, effectiveDuration);
      return () => clearTimeout(timer);
    }
  }, [effectiveDuration, onClose]);

  return (
    <div
      role="status"
      className={cn(
        'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm',
        STYLES[type] || STYLES.info
      )}
    >
      <Icon
        className={cn(
          'mt-0.5 h-5 w-5 shrink-0',
          type === 'success' && 'text-success',
          type === 'error' && 'text-destructive',
          type === 'warning' && 'text-warning',
          type === 'info' && 'text-primary'
        )}
        aria-hidden
      />
      <p className="flex-1 text-sm font-medium leading-snug">{message}</p>
      <button
        type="button"
        onClick={onClose}
        className="rounded-md p-1 text-muted-foreground hover:bg-background/80 hover:text-foreground"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};

export default Toast;
