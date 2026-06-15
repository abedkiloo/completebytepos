import React from 'react';
import { Button } from '../ui/button';
import { cn } from '../../lib/cn';

/**
 * "Page X of Y" bar with prev/next. Returns null when a single page holds all rows.
 */
export function ListPagination({
  page,
  pageSize,
  totalCount = 0,
  onPageChange,
  suffix = null,
  className,
}) {
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize) || 1);
  if (!totalCount || totalCount <= pageSize) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 text-sm',
        className
      )}
    >
      <span className="text-muted-foreground">
        Page {page} of {totalPages}
        {suffix ? ` · ${suffix}` : ''}
      </span>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

/** Pagination above and below list content (same controls in both places). */
export function ListPaginationRail({ children, className, ...paginationProps }) {
  return (
    <div className={cn('space-y-3', className)}>
      <ListPagination {...paginationProps} />
      {children}
      <ListPagination {...paginationProps} />
    </div>
  );
}
