import React from 'react';
import { cn } from '../../lib/cn';

/**
 * Native scroll container (replaces Radix ScrollArea for reliable wheel/touch/trackpad).
 * Radix custom scrollbars often fail to scroll to the end and are hard to drag.
 */
const ScrollArea = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('app-scroll-region relative', className)}
    {...props}
  >
    {children}
  </div>
));
ScrollArea.displayName = 'ScrollArea';

/** Kept for API compatibility; native scrollbars are used instead. */
const ScrollBar = () => null;
ScrollBar.displayName = 'ScrollBar';

export { ScrollArea, ScrollBar };
