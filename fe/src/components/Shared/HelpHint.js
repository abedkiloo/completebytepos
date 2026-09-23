import React, { useEffect, useRef, useState } from 'react';
import { HelpCircle } from 'lucide-react';
import { cn } from '../../lib/cn';
import { getActionHelp } from '../../utils/actionHelp';

/**
 * Hover (desktop) or tap (touch) help so people can read what an action does
 * before they confirm it.
 */
export default function HelpHint({
  actionKey,
  title,
  body,
  contrast,
  label,
  className,
  side = 'bottom',
}) {
  const help = getActionHelp(actionKey);
  const resolvedTitle = title || help.title;
  const resolvedBody = body || help.hover;
  const resolvedContrast = contrast === undefined ? help.contrast : contrast;
  const ariaLabel = label || `What is ${help.shortLabel}?`;
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span
      ref={rootRef}
      className={cn('relative inline-flex align-middle', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-label={ariaLabel}
        aria-expanded={open}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpen((prev) => !prev);
        }}
      >
        <HelpCircle className="h-3.5 w-3.5" aria-hidden />
      </button>
      {open ? (
        <span
          role="tooltip"
          className={cn(
            'absolute z-[3200] w-64 rounded-md border bg-popover p-3 text-left text-xs text-popover-foreground shadow-md',
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
            'right-0 sm:left-1/2 sm:right-auto sm:-translate-x-1/2'
          )}
        >
          <span className="block font-semibold text-foreground">{resolvedTitle}</span>
          <span className="mt-1 block leading-relaxed text-muted-foreground">{resolvedBody}</span>
          {resolvedContrast ? (
            <span className="mt-2 block leading-relaxed text-amber-800 dark:text-amber-200">
              {resolvedContrast}
            </span>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
