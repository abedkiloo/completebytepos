import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { ClipboardCheck, Loader2, Check, X } from 'lucide-react';
import { expensesAPI, pendingChangesAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading } from '../page';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { userMayEditFinancialFieldsFromStorage } from '../../utils/roleAccess';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import {
  canApproveFinancialRecord,
  needsExtremePriceConfirm,
} from '../../utils/makerChecker';
import { describeApprovalSummary, formatApprovalValue } from '../../utils/approvalDisplay';
import { backfillRejectionSuccessMessage } from '../../utils/recordPastSaleBackfill';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ApprovalChangeTable from './ApprovalChangeTable';

function PendingRow({ row, onResolved }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [extremeConfirm, setExtremeConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const extremeRequired = needsExtremePriceConfirm(row);
  const { headline, action, item } = describeApprovalSummary(row);

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
      toast.warning('Please say why you are rejecting this change');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.reject(row.id, { rejection_reason: rejectReason.trim() });
      toast.success(backfillRejectionSuccessMessage(row.action_type));
      onResolved();
      dispatchNavBadgesRefresh();
    } catch {
      toast.error('Could not reject this change');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-l-4 border-l-amber-400">
      <CardContent className="space-y-4 pt-6">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{action}</Badge>
            {row.batch_id ? (
              <Badge variant="outline" className="text-[10px]">
                Grouped request
              </Badge>
            ) : null}
          </div>
          <h3 className="text-base font-semibold leading-snug">{item}</h3>
          <p className="text-xs text-muted-foreground">
            Requested by {row.made_by_username || 'a team member'} ·{' '}
            {formatDateTime(row.made_at)}
          </p>
        </div>

        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm">
          <span className="font-medium">Why they asked: </span>
          {row.reason || 'No reason provided'}
        </div>

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Review the change
          </p>
          <ApprovalChangeTable
            originalValues={row.original_values}
            proposedValues={row.proposed_values}
          />
        </div>

        {extremeRequired ? (
          <div className="rounded-md border border-amber-300 bg-amber-50/90 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
            <p className="font-medium text-amber-900 dark:text-amber-100">
              Large price change (more than 50% from the current price)
            </p>
            <p className="mt-1 text-muted-foreground">
              Current: {formatApprovalValue('price', row.original_values?.price)} → Requested:{' '}
              {formatApprovalValue('price', row.proposed_values?.price)}
            </p>
            <label className="mt-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={extremeConfirm}
                onChange={(e) => setExtremeConfirm(e.target.checked)}
              />
              I have verified this price change is correct
            </label>
          </div>
        ) : row.action_type === 'product_price' ? (
          <p className="text-xs text-muted-foreground">
            Price change is within the normal approval range.
          </p>
        ) : null}

        {showReject ? (
          <div className="space-y-2">
            <Label>Why are you rejecting this?</Label>
            <Input
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Price is too low for this season"
            />
            <div className="flex gap-2">
              <Button type="button" variant="destructive" size="sm" onClick={reject} disabled={busy}>
                Confirm rejection
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowReject(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={approve}
              disabled={busy || (extremeRequired && !extremeConfirm)}
            >
              <Check className="mr-1 h-4 w-4" />
              Approve change
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
          </div>
        )}

        <p className="sr-only">{headline}</p>
      </CardContent>
    </Card>
  );
}

function PendingExpenseRow({ expense, settings, onResolved }) {
  const [busy, setBusy] = useState(false);
  const canApprove = canApproveFinancialRecord(
    expense,
    settings,
    undefined,
    'expenses',
  );

  const approve = async () => {
    setBusy(true);
    try {
      await expensesAPI.approve(expense.id);
      toast.success('Expense approved');
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      toast.error(
        err.response?.data?.error ||
          'Could not approve this expense',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-l-4 border-l-amber-400">
      <CardContent className="space-y-4 pt-6">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">Expense approval</Badge>
            <Badge variant="outline">{formatCurrency(expense.amount)}</Badge>
          </div>
          <h3 className="text-base font-semibold leading-snug">
            {expense.description || expense.expense_number}
          </h3>
          <p className="text-xs text-muted-foreground">
            Requested by {expense.created_by_name || 'a team member'} ·{' '}
            {formatDateTime(expense.created_at)}
          </p>
        </div>

        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm">
          <p><span className="font-medium">Reference: </span>{expense.expense_number}</p>
          <p><span className="font-medium">Category: </span>{expense.category_name || '—'}</p>
          {expense.vendor ? (
            <p><span className="font-medium">Vendor: </span>{expense.vendor}</p>
          ) : null}
        </div>

        {canApprove ? (
          <Button type="button" size="sm" onClick={approve} disabled={busy}>
            <Check className="mr-1 h-4 w-4" />
            Approve expense
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">
            This submission requires approval from another checker.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function PendingApprovalsPage() {
  const allowed = userMayEditFinancialFieldsFromStorage();
  const [rows, setRows] = useState([]);
  const [pendingExpenses, setPendingExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
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
      setRows(Array.isArray(changesResult.value.data) ? changesResult.value.data : []);
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

    if (
      changesResult.status === 'rejected' &&
      expensesResult.status === 'rejected'
    ) {
      toast.error('Could not load pending approvals');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Approvals waiting for you"
        description="Review financial, price, stock, and catalog changes from your team before they go live."
        icon={ClipboardCheck}
      />
      <div className="mb-4 flex justify-end">
        <Button type="button" variant="outline" onClick={load} disabled={loading}>
          Refresh list
        </Button>
      </div>
      {loading ? (
        <PageLoading />
      ) : rows.length === 0 && pendingExpenses.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            All clear — no changes waiting for your approval.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {pendingExpenses.map((expense) => (
            <PendingExpenseRow
              key={`expense-${expense.id}`}
              expense={expense}
              settings={storeSettings}
              onResolved={load}
            />
          ))}
          {rows.map((row) => (
            <PendingRow key={row.id} row={row} onResolved={load} />
          ))}
        </div>
      )}
      {loading && rows.length > 0 ? (
        <div className="flex justify-center py-4">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : null}
    </PageShell>
  );
}
