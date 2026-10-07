import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, X, History } from 'lucide-react';
import { expensesAPI, pendingChangesAPI } from '../../services/api';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { PageLoading } from '../page';
import { toast } from '../../utils/toast';
import { formatDateTime } from '../../utils/formatters';
import { getStoredAuth } from '../../utils/roleAccess';
import {
  formatExpenseDecisionRow,
  formatMyDecisionRow,
  DECISION_STATUS_APPROVED,
  DECISION_STATUS_REJECTED,
} from '../../utils/approvalDecisions';
import ApprovalChangeTable from './ApprovalChangeTable';
import ApprovalDetails from './ApprovalDetails';
import { expenseApprovalDetails } from '../../utils/approvalDisplay';
import { cn } from '../../lib/cn';

/**
 * Accountability trail of items the signed-in checker has already decided.
 */
export default function MyDecisionsTrail({
  actionTypes = null,
  includeExpenses = false,
  emptyTitle = 'No decisions yet',
  emptyDescription = 'When you approve or reject a request, it will show here with the time and any comments.',
}) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const params = { limit: 50 };
    if (statusFilter === DECISION_STATUS_APPROVED || statusFilter === DECISION_STATUS_REJECTED) {
      params.status = statusFilter;
    }
    if (Array.isArray(actionTypes) && actionTypes.length === 1) {
      params.action_type = actionTypes[0];
    }

    const tasks = [pendingChangesAPI.myDecisions(params)];
    const { user } = getStoredAuth();
    if (includeExpenses && user?.id && statusFilter !== DECISION_STATUS_REJECTED) {
      tasks.push(
        expensesAPI.list({
          status: 'approved',
          approved_by: user.id,
          show_all: 'true',
          page_size: 50,
        }),
      );
    }

    const results = await Promise.allSettled(tasks);
    const decisions = [];

    if (results[0]?.status === 'fulfilled') {
      let data = results[0].value.data;
      data = Array.isArray(data) ? data : data?.results || [];
      if (Array.isArray(actionTypes) && actionTypes.length > 1) {
        const allowed = new Set(actionTypes);
        data = data.filter((row) => allowed.has(row.action_type));
      }
      decisions.push(...data.map(formatMyDecisionRow));
    }

    if (results[1]?.status === 'fulfilled') {
      const data = results[1].value.data;
      const expenses = data?.results || data || [];
      if (Array.isArray(expenses)) {
        decisions.push(...expenses.map(formatExpenseDecisionRow));
      }
    }

    if (results.every((r) => r.status === 'rejected')) {
      toast.error('Could not load your approval history');
      setRows([]);
    } else {
      decisions.sort((a, b) => {
        const ta = a.decidedAt ? new Date(a.decidedAt).getTime() : 0;
        const tb = b.decidedAt ? new Date(b.decidedAt).getTime() : 0;
        return tb - ta;
      });
      setRows(decisions);
    }
    setLoading(false);
  }, [actionTypes, includeExpenses, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const filters = useMemo(
    () => [
      { id: 'all', label: 'All' },
      { id: DECISION_STATUS_APPROVED, label: 'Approved' },
      { id: DECISION_STATUS_REJECTED, label: 'Rejected' },
    ],
    [],
  );

  return (
    <div className="space-y-4" data-testid="my-decisions-trail">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {filters.map((f) => (
            <Button
              key={f.id}
              type="button"
              size="sm"
              variant={statusFilter === f.id ? 'default' : 'outline'}
              onClick={() => setStatusFilter(f.id)}
              aria-pressed={statusFilter === f.id}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <PageLoading rows={4} />
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <History className="h-8 w-8 opacity-50" aria-hidden />
            <p className="font-medium text-foreground">{emptyTitle}</p>
            <p className="max-w-md text-sm">{emptyDescription}</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="border-b bg-muted/30 px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {rows.length} decision{rows.length === 1 ? '' : 's'}
            </div>
            <ul>
              {rows.map((row) => {
                const approved = row.status === DECISION_STATUS_APPROVED;
                return (
                  <li key={row.key}>
                    <button
                      type="button"
                      onClick={() => setSelected(row)}
                      className={cn(
                        'flex w-full items-start gap-3 border-b border-border/60 px-3 py-3 text-left transition-colors',
                        'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      )}
                      data-testid="my-decision-row"
                    >
                      <span
                        className={cn(
                          'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                          approved
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800',
                        )}
                        aria-hidden
                      >
                        {approved ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant={approved ? 'default' : 'destructive'}
                            className="shrink-0 text-[10px]"
                          >
                            {row.statusLabel}
                          </Badge>
                          <Badge variant="secondary" className="shrink-0 text-[10px]">
                            {row.badge}
                          </Badge>
                          <span className="truncate text-sm font-medium">{row.title}</span>
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          Requested by {row.requestedBy}
                          {row.decidedAt
                            ? ` · You decided ${formatDateTime(row.decidedAt)}`
                            : null}
                        </p>
                        {row.comment ? (
                          <p className="mt-1 line-clamp-2 text-xs text-foreground/80">
                            <span className="font-medium">{row.commentLabel}: </span>
                            {row.comment}
                          </p>
                        ) : null}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent
          className="max-h-[90vh] max-w-2xl overflow-y-auto"
          description="Accountability record for a request you already decided."
        >
          {selected ? (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8">{selected.headline || selected.title}</DialogTitle>
                <DialogDescription>
                  {selected.statusLabel}
                  {selected.decidedAt
                    ? ` · ${formatDateTime(selected.decidedAt)}`
                    : null}
                  {` · Requested by ${selected.requestedBy}`}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 text-sm">
                {selected.requesterReason ? (
                  <div className="rounded-md border bg-muted/30 px-3 py-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Requester reason
                    </p>
                    <p className="mt-1 whitespace-pre-wrap">{selected.requesterReason}</p>
                  </div>
                ) : null}
                {selected.checkerComment ? (
                  <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 dark:border-rose-900 dark:bg-rose-950/40">
                    <p className="text-xs font-medium uppercase tracking-wide text-rose-800 dark:text-rose-200">
                      Your comment on reject
                    </p>
                    <p className="mt-1 whitespace-pre-wrap">{selected.checkerComment}</p>
                  </div>
                ) : null}
                {selected.kind === 'expense' ? (
                  <ApprovalDetails details={expenseApprovalDetails(selected.data)} />
                ) : (
                  <ApprovalChangeTable
                    originalValues={selected.data?.original_values}
                    proposedValues={selected.data?.proposed_values}
                  />
                )}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
