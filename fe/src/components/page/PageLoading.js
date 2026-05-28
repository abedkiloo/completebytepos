import React from 'react';
import { Skeleton } from '../ui/skeleton';
import { PageShell } from './PageShell';

export function PageLoading({ rows = 6, showStats = false }) {
  return (
    <PageShell>
      <Skeleton className="h-10 w-56" />
      <Skeleton className="h-4 w-72 max-w-full" />
      {showStats && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
      )}
      <Skeleton className="h-11 w-full max-w-md rounded-md" />
      <div className="space-y-2 rounded-lg border bg-card p-4">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </PageShell>
  );
}
