import React from 'react';
import { Button } from '../ui/button';

/**
 * Standard footer for paginated list screens: "Page X of Y" with prev/next.
 */
export function ListPagination({
  page,
  pageSize,
  totalCount = 0,
  onPageChange,
  suffix = null,
}) {
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize) || 1);
  if (!totalCount || totalCount <= pageSize) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 text-sm">
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
