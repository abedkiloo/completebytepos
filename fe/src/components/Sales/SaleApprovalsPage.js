import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Check, CheckCircle2, Loader2, X } from 'lucide-react';
import { pendingChangesAPI, salesAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { getStoredAuth } from '../../utils/roleAccess';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { saleDisplayItemCount } from '../../utils/saleItemDisplay';
import {
  partitionSaleApprovalQueue,
  saleNeedsSalespersonAction,
  saleRejectionReason,
  userCanApproveSales,
} from '../../utils/saleCompletionApproval';
import { rejectionReturnedMessage } from '../../utils/approvalReturn';
import {
  collectionAmount,
  collectionMethod,
  pendingDebtCollectionParams,
  saleApprovalsEmpty,
  userCanApproveDebtCollections,
  userCanOpenSaleApprovals,
} from '../../utils/saleApprovalsQueue';
import HelpHint from '../Shared/HelpHint';
import PastDatedNotice from '../Approvals/PastDatedNotice';
import {
  isPastDated,
  pastDatedBlocksUser,
  pendingChangeDates,
  userMayApprovePastItems,
} from '../../utils/pastDatedApproval';

function SaleApprovalRow({ sale, onResolved }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const itemCount = saleDisplayItemCount(sale);
  const returned = saleNeedsSalespersonAction(sale);
  const managerComment = saleRejectionReason(sale);
  const saleDates = [sale.occurred_at || sale.created_at];
  const pastDated = isPastDated(...saleDates);
  const adminOnly = pastDatedBlocksUser(saleDates);

  const approve = async () => {
    setBusy(true);
    try {
      await salesAPI.complete(sale.id);
      toast.success(`Sale ${sale.sale_number} approved. Stock, books, and the receipt are live.`);
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.detail || 'Could not approve this sale');
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) {
      toast.warning('Please say why you are returning this sale');
      return;
    }
    setBusy(true);
    try {
      await salesAPI.rejectComplete(sale.id, { rejection_reason: rejectReason.trim() });
      toast.success(rejectionReturnedMessage('sale_complete'));
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.rejection_reason || 'Could not reject this sale');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{sale.sale_number}</p>
            <p className="truncate text-sm text-muted-foreground">
              {sale.cashier_name || 'Cashier'} · {formatDateTime(sale.occurred_at || sale.created_at)}
            </p>
          </div>
          <div className="min-w-0 shrink-0 text-right">
            <p className="truncate font-semibold">{formatCurrency(sale.total)}</p>
            <Badge variant="outline">
              {Number(sale.amount_paid || 0) < Number(sale.total || 0)
                ? `Paid ${formatCurrency(sale.amount_paid || 0)} · debt remaining`
                : `Paid ${formatCurrency(sale.amount_paid || sale.total || 0)}`}
            </Badge>
            {returned ? (
              <Badge variant="destructive" className="mt-1">
                Needs salesperson action
              </Badge>
            ) : null}
          </div>
        </div>
        <p className="truncate text-sm text-muted-foreground">
          {itemCount} line{itemCount === 1 ? '' : 's'}
          {sale.customer_name ? ` · ${sale.customer_name}` : ''}
        </p>
        {returned ? (
          <div className="space-y-1 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm">
            <p className="font-medium text-amber-950">
              Waiting on the salesperson to fix this sale and send it again.
            </p>
            {managerComment ? (
              <p className="text-amber-900">Manager comment: {managerComment}</p>
            ) : null}
            <p className="text-xs text-amber-800">A sticky Daily note was also sent to them.</p>
          </div>
        ) : adminOnly ? (
          <PastDatedNotice dates={saleDates} blocked />
        ) : (
          <>
        {pastDated ? <PastDatedNotice dates={saleDates} blocked={false} /> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={approve} disabled={busy}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <HelpHint actionKey="sale_complete" />
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowReject((open) => !open)}
            disabled={busy}
          >
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
        </div>
        {showReject ? (
          <div className="space-y-2">
            <Label htmlFor={`reject-${sale.id}`}>Reason</Label>
            <Input
              id={`reject-${sale.id}`}
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="Why should this sale not complete?"
            />
            <Button size="sm" variant="destructive" onClick={reject} disabled={busy}>
              Confirm reject
            </Button>
          </div>
        ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function DebtCollectionApprovalRow({ change, onResolved }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const amount = collectionAmount(change);
  const method = collectionMethod(change);
  const dates = pendingChangeDates(change);
  const pastDated = Boolean(change.past_dated) || isPastDated(...dates);
  const adminOnly = pastDated && !userMayApprovePastItems();

  const approve = async () => {
    setBusy(true);
    try {
      await pendingChangesAPI.approve(change.id);
      toast.success(
        `Collection for ${change.entity_repr || 'customer'} approved. The wallet is updated.`
      );
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.detail || 'Could not approve this collection');
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) {
      toast.warning('Please say why you are returning this collection');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.reject(change.id, { rejection_reason: rejectReason.trim() });
      toast.success('Collection was returned. The customer wallet was not changed.');
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.rejection_reason || 'Could not reject this collection');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-semibold">{change.entity_repr || 'Customer'}</p>
            <p className="truncate text-sm text-muted-foreground">
              {change.made_by_username || 'Salesperson'} · {formatDateTime(change.made_at)}
            </p>
          </div>
          <div className="min-w-0 shrink-0 text-right">
            <p className="truncate font-semibold">{formatCurrency(amount)}</p>
            <Badge variant="outline" className="capitalize">
              {method}
            </Badge>
          </div>
        </div>
        <p className="truncate text-sm text-muted-foreground">
          Debt collection
          {change.reason ? ` · ${change.reason}` : ''}
        </p>
        {pastDated ? <PastDatedNotice dates={dates} blocked={adminOnly} /> : null}
        {adminOnly ? null : (
          <>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={approve} disabled={busy}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <HelpHint actionKey="debt_collection" />
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowReject((open) => !open)}
            disabled={busy}
          >
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
        </div>
        {showReject ? (
          <div className="space-y-2">
            <Label htmlFor={`reject-collection-${change.id}`}>Reason</Label>
            <Input
              id={`reject-collection-${change.id}`}
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              placeholder="Why should this collection not apply?"
            />
            <Button size="sm" variant="destructive" onClick={reject} disabled={busy}>
              Confirm reject
            </Button>
          </div>
        ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function SaleApprovalsPage() {
  const { permissions } = getStoredAuth();
  const allowed = userCanOpenSaleApprovals(permissions);
  const canSales = userCanApproveSales(permissions);
  const canCollections = userCanApproveDebtCollections(permissions);
  const [sales, setSales] = useState([]);
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tasks = [];
      if (canSales) {
        tasks.push(
          salesAPI
            .list({ status: 'pending_approval', page_size: 100 })
            .then((response) => {
              const data = response.data;
              setSales(data.results || (Array.isArray(data) ? data : []));
            })
        );
      } else {
        setSales([]);
      }
      if (canCollections) {
        tasks.push(
          pendingChangesAPI.pending(pendingDebtCollectionParams()).then((response) => {
            const data = response.data;
            setCollections(Array.isArray(data) ? data : data?.results || []);
          })
        );
      } else {
        setCollections([]);
      }
      const results = await Promise.allSettled(tasks);
      if (results.some((result) => result.status === 'rejected')) {
        toast.error('Could not load items waiting for approval');
      }
    } catch (error) {
      setSales([]);
      setCollections([]);
      toast.error('Could not load items waiting for approval');
    } finally {
      setLoading(false);
    }
  }, [canSales, canCollections]);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  const empty = saleApprovalsEmpty({ sales, collections });
  const { waiting: waitingSales, returned: returnedSales } = partitionSaleApprovalQueue(sales);

  return (
    <PageShell>
      <PageHeader
        title="Approve sales"
        description="Review cashier sales (payment and any remaining debt included) before stock and books go live. Salesperson debt collections wait here before the customer wallet changes. Both permissions are set on Roles."
        icon={CheckCircle2}
      >
        <Button type="button" variant="outline" onClick={load} disabled={loading}>
          Refresh list
        </Button>
      </PageHeader>
      {loading ? (
        <PageLoading />
      ) : empty ? (
        <EmptyState
          title="Nothing waiting"
          description="New cashier checkouts and salesperson collections will appear here."
        />
      ) : (
        <div className="space-y-6">
          {canSales && sales.length > 0 ? (
            <>
              {waitingSales.length > 0 ? (
                <section className="space-y-3">
                  <h2 className="text-sm font-semibold text-muted-foreground">Cashier sales</h2>
                  {waitingSales.map((sale) => (
                    <SaleApprovalRow key={`sale-${sale.id}`} sale={sale} onResolved={load} />
                  ))}
                </section>
              ) : null}
              {returnedSales.length > 0 ? (
                <section className="space-y-3">
                  <h2 className="text-sm font-semibold text-muted-foreground">
                    Needs salesperson action
                  </h2>
                  {returnedSales.map((sale) => (
                    <SaleApprovalRow key={`sale-${sale.id}`} sale={sale} onResolved={load} />
                  ))}
                </section>
              ) : null}
            </>
          ) : null}
          {canCollections && collections.length > 0 ? (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground">Debt collections</h2>
              {collections.map((change) => (
                <DebtCollectionApprovalRow
                  key={`collection-${change.id}`}
                  change={change}
                  onResolved={load}
                />
              ))}
            </section>
          ) : null}
        </div>
      )}
    </PageShell>
  );
}
