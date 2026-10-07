import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { ClipboardCheck, Loader2, Check, X, ChevronRight } from 'lucide-react';
import { expensesAPI, pendingChangesAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading } from '../page';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { userMayEditFinancialFieldsFromStorage } from '../../utils/roleAccess';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import {
  canApproveFinancialRecord,
  needsExtremePriceConfirm,
} from '../../utils/makerChecker';
import {
  describeApprovalSummary,
  expenseApprovalDetails,
  formatApprovalValue,
} from '../../utils/approvalDisplay';
import { otherPendingApprovalRows } from '../../utils/saleApprovalsQueue';
import { backfillRejectionSuccessMessage } from '../../utils/recordPastSaleBackfill';
import { getActionHelp } from '../../utils/actionHelp';
import HelpHint from '../Shared/HelpHint';
import CenterScreenLoader from '../Shared/CenterScreenLoader';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ApprovalChangeTable from './ApprovalChangeTable';
import ApprovalDetails from './ApprovalDetails';
import PastDatedNotice from './PastDatedNotice';
import {
  isPastDated,
  pastDatedBlocksUser,
  pendingChangeDates,
  userMayApprovePastItems,
} from '../../utils/pastDatedApproval';
import CommitConfirm from '../Shared/CommitConfirm';
import { approvalCommitRows, approvalExpenseRows } from '../../utils/formCommitSummary';
import { cn } from '../../lib/cn';
import MyDecisionsTrail from './MyDecisionsTrail';

const KIND_CHANGE = 'change';
const KIND_EXPENSE = 'expense';
const TAB_WAITING = 'waiting';
const TAB_HISTORY = 'history';

function ApprovalListRow({ title, subtitle, badge, amount, selected, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex w-full items-center gap-3 border-b border-border/60 px-3 py-2.5 text-left transition-colors',
        'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected && 'bg-primary/5',
      )}
      data-testid="approval-list-row"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="shrink-0 text-[10px]">
            {badge}
          </Badge>
          <span className="truncate text-sm font-medium">{title}</span>
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtitle}</p>
      </div>
      {amount != null ? (
        <span className="shrink-0 text-sm font-semibold tabular-nums">{formatCurrency(amount)}</span>
      ) : null}
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
    </button>
  );
}

function ChangeReviewBody({ row }) {
  const extremeRequired = needsExtremePriceConfirm(row);
  const dates = pendingChangeDates(row);
  const pastDated = Boolean(row.past_dated) || isPastDated(...dates);
  const adminOnly = pastDated && !userMayApprovePastItems();

  return (
    <div className="space-y-4">
      <div className="rounded-md bg-muted/30 px-3 py-2 text-sm">
        <span className="font-medium">Why they asked: </span>
        {row.reason || 'No reason provided'}
      </div>

      <ApprovalDetails details={row.details} />

      {row.action_type === 'sale_backfill' && row.details ? null : (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Review the change
          </p>
          <ApprovalChangeTable
            originalValues={row.original_values}
            proposedValues={row.proposed_values}
          />
        </div>
      )}

      {extremeRequired ? (
        <div className="rounded-md border border-amber-300 bg-amber-50/90 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
          <p className="font-medium text-amber-900 dark:text-amber-100">
            Large price change (more than 50% from the current price)
          </p>
          <p className="mt-1 text-muted-foreground">
            Current: {formatApprovalValue('price', row.original_values?.price)} → Requested:{' '}
            {formatApprovalValue('price', row.proposed_values?.price)}
          </p>
        </div>
      ) : row.action_type === 'product_price' ? (
        <p className="text-xs text-muted-foreground">
          Price change is within the normal approval range.
        </p>
      ) : null}

      {pastDated ? <PastDatedNotice dates={dates} blocked={adminOnly} /> : null}
    </div>
  );
}

function ChangeReviewActions({ row, onResolved, onClose }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [extremeConfirm, setExtremeConfirm] = useState(false);
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const extremeRequired = needsExtremePriceConfirm(row);
  const dates = pendingChangeDates(row);
  const pastDated = Boolean(row.past_dated) || isPastDated(...dates);
  const adminOnly = pastDated && !userMayApprovePastItems();

  const requestApprove = () => {
    if (extremeRequired && !extremeConfirm) {
      toast.warning('Please confirm the large price change before approving.');
      return;
    }
    setShowApproveConfirm(true);
  };

  const approve = async () => {
    if (extremeRequired && !extremeConfirm) {
      toast.warning('Please confirm the large price change before approving.');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.approve(row.id, {
        extreme_price_confirmed: extremeRequired ? extremeConfirm : false,
      });
      toast.success('Approved — the change is now live');
      setShowApproveConfirm(false);
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      const msg =
        (typeof data === 'object' && (data.error || Object.values(data).flat().join(', '))) ||
        data?.detail ||
        'Could not approve this change';
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) {
      toast.warning('Please say why you are returning this change');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.reject(row.id, { rejection_reason: rejectReason.trim() });
      toast.success(backfillRejectionSuccessMessage(row.action_type));
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch {
      toast.error('Could not reject this change');
    } finally {
      setBusy(false);
    }
  };

  if (adminOnly) return null;

  return (
    <>
      {extremeRequired ? (
        <label className="mb-2 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={extremeConfirm}
            onChange={(e) => setExtremeConfirm(e.target.checked)}
          />
          I have verified this price change is correct
        </label>
      ) : null}

      {showReject ? (
        <div className="w-full space-y-2">
          <Label>Why are you returning this to the requester?</Label>
          <Input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="e.g. Price is too low for this season"
          />
          <p className="text-xs text-muted-foreground">{getActionHelp('reject_change').hover}</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="destructive" size="sm" onClick={reject} disabled={busy}>
              Return to requester
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowReject(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={requestApprove}
            disabled={busy || (extremeRequired && !extremeConfirm)}
          >
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowReject(true)}
            disabled={busy}
          >
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
          <HelpHint actionKey="reject_change" />
        </div>
      )}

      <CommitConfirm
        open={showApproveConfirm}
        onOpenChange={(open) => {
          if (!open && !busy) setShowApproveConfirm(false);
        }}
        title="Approve this change?"
        description={getActionHelp('approve_change').confirmBody}
        helpKey="approve_change"
        rows={approvalCommitRows(row)}
        submitting={busy}
        confirmText="Confirm & approve"
        onConfirm={approve}
      />
      <CenterScreenLoader open={busy} label="Processing approval…" />
    </>
  );
}

function ExpenseReviewBody({ expense }) {
  const expenseDates = [expense.expense_date, expense.created_at];
  const pastDated = isPastDated(...expenseDates);
  const adminOnly = pastDatedBlocksUser(expenseDates);

  return (
    <div className="space-y-4">
      <ApprovalDetails details={expenseApprovalDetails(expense)} />
      {pastDated ? <PastDatedNotice dates={expenseDates} blocked={adminOnly} /> : null}
    </div>
  );
}

function ExpenseReviewActions({ expense, settings, onResolved, onClose }) {
  const [busy, setBusy] = useState(false);
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const canApprove = canApproveFinancialRecord(expense, settings, undefined, 'expenses');
  const expenseDates = [expense.expense_date, expense.created_at];
  const adminOnly = pastDatedBlocksUser(expenseDates);

  const approve = async () => {
    setBusy(true);
    try {
      await expensesAPI.approve(expense.id);
      toast.success('Expense approved');
      setShowApproveConfirm(false);
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      toast.error(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          'Could not approve this expense',
      );
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) {
      toast.warning('Please say why you are returning this expense');
      return;
    }
    setBusy(true);
    try {
      await expensesAPI.reject(expense.id, { rejection_reason: rejectReason.trim() });
      toast.success(backfillRejectionSuccessMessage('expense'));
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      toast.error(
        err.response?.data?.error ||
          err.response?.data?.detail ||
          'Could not return this expense',
      );
    } finally {
      setBusy(false);
    }
  };

  if (adminOnly) return null;

  if (!canApprove) {
    return (
      <p className="text-xs text-muted-foreground">
        Only an admin can approve or return expenses.
      </p>
    );
  }

  return (
    <>
      {showReject ? (
        <div className="w-full space-y-2">
          <Label>Why are you returning this expense?</Label>
          <Input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="e.g. Missing receipt"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="destructive" size="sm" onClick={reject} disabled={busy}>
              Return to requester
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowReject(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" onClick={() => setShowApproveConfirm(true)} disabled={busy}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowReject(true)}
            disabled={busy}
          >
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
          <HelpHint actionKey="reject_change" />
        </div>
      )}

      <CommitConfirm
        open={showApproveConfirm}
        onOpenChange={(open) => {
          if (!open && !busy) setShowApproveConfirm(false);
        }}
        title="Approve this expense?"
        description={getActionHelp('expense').confirmBody}
        helpKey="expense"
        rows={approvalExpenseRows(expense)}
        submitting={busy}
        confirmText="Confirm & approve"
        onConfirm={approve}
      />
      <CenterScreenLoader open={busy} label="Processing approval…" />
    </>
  );
}

function moneyFromDetails(details) {
  const sections = details?.sections || [];
  for (const section of sections) {
    for (const fact of section.facts || []) {
      if (fact.kind === 'money' && /total|amount|paid/i.test(fact.label || '')) {
        const n = Number(fact.value);
        if (Number.isFinite(n)) return n;
      }
    }
  }
  return null;
}

export default function PendingApprovalsPage() {
  const allowed = userMayEditFinancialFieldsFromStorage();
  const [tab, setTab] = useState(TAB_WAITING);
  const [rows, setRows] = useState([]);
  const [pendingExpenses, setPendingExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const { settings: storeSettings } = useStoreSettings();

  const load = useCallback(async () => {
    setLoading(true);
    const [changesResult, expensesResult] = await Promise.allSettled([
      pendingChangesAPI.pending(),
      expensesAPI.list({
        status: 'pending',
        show_all: 'true',
        page_size: 100,
      }),
    ]);

    if (changesResult.status === 'fulfilled') {
      const data = changesResult.value.data;
      setRows(otherPendingApprovalRows(Array.isArray(data) ? data : data?.results || []));
    } else {
      setRows([]);
    }

    if (expensesResult.status === 'fulfilled') {
      const data = expensesResult.value.data;
      const expenseRows = data?.results || data || [];
      setPendingExpenses(Array.isArray(expenseRows) ? expenseRows : []);
    } else {
      setPendingExpenses([]);
    }

    if (changesResult.status === 'rejected' && expensesResult.status === 'rejected') {
      toast.error('Could not load pending approvals');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (allowed && tab === TAB_WAITING) load();
  }, [allowed, load, tab]);

  const listItems = useMemo(() => {
    const expenses = pendingExpenses.map((expense) => ({
      key: `expense-${expense.id}`,
      kind: KIND_EXPENSE,
      id: expense.id,
      badge: 'Expense',
      title: expense.description || expense.expense_number || 'Expense',
      subtitle: `${expense.created_by_name || 'a team member'} · ${formatDateTime(expense.created_at)}`,
      amount: Number(expense.amount) || 0,
      data: expense,
    }));
    const changes = rows.map((row) => {
      const { action, item } = describeApprovalSummary(row);
      return {
        key: `change-${row.id}`,
        kind: KIND_CHANGE,
        id: row.id,
        badge: action,
        title: item,
        subtitle: `${row.made_by_username || 'a team member'} · ${formatDateTime(row.made_at)}`,
        amount: moneyFromDetails(row.details),
        data: row,
      };
    });
    return [...expenses, ...changes];
  }, [pendingExpenses, rows]);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  const selectedOpen = Boolean(selected);
  const selectedChange = selected?.kind === KIND_CHANGE ? selected.data : null;
  const selectedExpense = selected?.kind === KIND_EXPENSE ? selected.data : null;
  const dialogTitle = selected
    ? selected.kind === KIND_EXPENSE
      ? selected.title
      : describeApprovalSummary(selected.data).headline
    : 'Approval';

  return (
    <PageShell>
      <PageHeader
        title="Approvals"
        description="Review waiting requests, or open My decisions for a trail of what you already approved or rejected — with time and comments."
        icon={ClipboardCheck}
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Approvals views">
          <Button
            type="button"
            size="sm"
            variant={tab === TAB_WAITING ? 'default' : 'outline'}
            role="tab"
            aria-selected={tab === TAB_WAITING}
            onClick={() => setTab(TAB_WAITING)}
          >
            Waiting
            {listItems.length > 0 ? ` (${listItems.length})` : ''}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={tab === TAB_HISTORY ? 'default' : 'outline'}
            role="tab"
            aria-selected={tab === TAB_HISTORY}
            onClick={() => setTab(TAB_HISTORY)}
          >
            My decisions
          </Button>
        </div>
        {tab === TAB_WAITING ? (
          <Button type="button" variant="outline" onClick={load} disabled={loading}>
            Refresh list
          </Button>
        ) : null}
      </div>

      {tab === TAB_HISTORY ? (
        <MyDecisionsTrail includeExpenses />
      ) : loading ? (
        <PageLoading />
      ) : listItems.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            All clear — no changes waiting for your approval.
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="border-b bg-muted/30 px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {listItems.length} waiting
            </div>
            <div data-testid="approval-list">
              {listItems.map((item) => (
                <ApprovalListRow
                  key={item.key}
                  title={item.title}
                  subtitle={item.subtitle}
                  badge={item.badge}
                  amount={item.amount}
                  selected={selected?.key === item.key}
                  onOpen={() => setSelected(item)}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={selectedOpen}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent
          className="max-h-[90vh] max-w-2xl overflow-y-auto"
          description="Review this approval request, then approve or reject."
        >
          <DialogHeader>
            <DialogTitle className="pr-8">{dialogTitle}</DialogTitle>
            <DialogDescription>
              {selected
                ? `Requested by ${
                    selected.kind === KIND_EXPENSE
                      ? selected.data.created_by_name || 'a team member'
                      : selected.data.made_by_username || 'a team member'
                  } · ${formatDateTime(
                    selected.kind === KIND_EXPENSE
                      ? selected.data.created_at
                      : selected.data.made_at,
                  )}`
                : 'Review and decide'}
            </DialogDescription>
          </DialogHeader>

          {selectedChange ? <ChangeReviewBody row={selectedChange} /> : null}
          {selectedExpense ? <ExpenseReviewBody expense={selectedExpense} /> : null}

          <DialogFooter className="flex-col items-stretch gap-2 sm:flex-col sm:space-x-0">
            {selectedChange ? (
              <ChangeReviewActions
                key={`actions-change-${selectedChange.id}`}
                row={selectedChange}
                onResolved={load}
                onClose={() => setSelected(null)}
              />
            ) : null}
            {selectedExpense ? (
              <ExpenseReviewActions
                key={`actions-expense-${selectedExpense.id}`}
                expense={selectedExpense}
                settings={storeSettings}
                onResolved={load}
                onClose={() => setSelected(null)}
              />
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
