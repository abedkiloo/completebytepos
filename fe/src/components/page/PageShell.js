import React from 'react';
import { cn } from '../../lib/cn';

/**
 * Standard page container — matches Dashboard spacing and max width.
 * Wrap every Layout child page in this for consistent rhythm.
 */
export function PageShell({ children, className, narrow }) {
  return (
    <div
      className={cn(
        'mx-auto w-full space-y-3 p-2 md:p-3',
        narrow ? 'max-w-4xl' : 'max-w-7xl',
        className
      )}
    >
      {children}
    </div>
  );
}
