import React, { useEffect, useId, useRef, useState } from 'react';

import { Badge } from '../ui/badge';
import { cn } from '../../lib/cn';
import {
  engagementTierLabel,
  engagementTierTooltip,
  buyerSegmentLabel,
  buyerSegmentTooltip,
  formatPurchaseCount,
} from '../../utils/customerIntelligence';

/**
 * Badge with hover / focus / tap explanation of a classification label.
 */
export function ClassificationBadge({
  label,
  tip,
  variant = 'default',
  className,
  size = 'sm',
}) {
  const [open, setOpen] = useState(false);
  const tipId = useId();
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

  if (!label || !tip) return null;

  return (
    <span
      ref={rootRef}
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <Badge
        variant={variant}
        title={tip}
        aria-describedby={open ? tipId : undefined}
        tabIndex={0}
        role="img"
        aria-label={`${label}. ${tip}`}
        className={cn(
          'cursor-help',
          size === 'sm' && 'px-1.5 py-0 text-[10px]',
          className
        )}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(event) => {
          // Tap on touch devices; do not bubble to row navigation.
          event.stopPropagation();
          setOpen((prev) => !prev);
        }}
      >
        {label}
      </Badge>
      {open ? (
        <span
          id={tipId}
          role="tooltip"
          className={cn(
            'absolute left-0 top-full z-50 mt-1 w-56 max-w-[min(14rem,70vw)]',
            'rounded-md border bg-popover px-2.5 py-2 text-left text-xs font-normal',
            'leading-snug text-popover-foreground shadow-md'
          )}
        >
          {tip}
        </span>
      ) : null}
    </span>
  );
}

/** Tier + segment badges for a customer row or detail header. */
export function CustomerClassificationBadges({
  engagementTier,
  buyerSegment,
  purchaseCount,
  size = 'sm',
  className,
  showPurchaseCount = false,
}) {
  const tierLabel = engagementTierLabel(engagementTier);
  const tierTip = engagementTierTooltip(engagementTier);
  const segLabel =
    engagementTier === 'buyer' ? buyerSegmentLabel(buyerSegment) : '';
  const segTip =
    engagementTier === 'buyer' ? buyerSegmentTooltip(buyerSegment) : '';

  if (!tierLabel && !segLabel) return null;

  return (
    <div className={cn('flex flex-wrap items-center gap-1', className)}>
      {tierLabel ? (
        <ClassificationBadge
          label={tierLabel}
          tip={tierTip}
          variant={engagementTier === 'buyer' ? 'default' : 'outline'}
          size={size}
        />
      ) : null}
      {segLabel ? (
        <ClassificationBadge
          label={segLabel}
          tip={segTip}
          variant="secondary"
          size={size}
        />
      ) : null}
      {showPurchaseCount &&
      engagementTier === 'buyer' &&
      Number(purchaseCount) > 0 ? (
        <span
          className={cn(
            'text-muted-foreground',
            size === 'sm' ? 'text-[10px]' : 'text-sm'
          )}
        >
          {formatPurchaseCount(purchaseCount)}
        </span>
      ) : null}
    </div>
  );
}
