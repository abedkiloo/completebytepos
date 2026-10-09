import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Check, CheckCircle2, ChevronRight, Loader2, X } from 'lucide-react';
import { pendingChangesAPI, salesAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
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
import CenterScreenLoader from '../Shared/CenterScreenLoader';
import PastDatedNotice from '../Approvals/PastDatedNotice';
import ApprovalDetails from '../Approvals/ApprovalDetails';
import MyDecisionsTrail from '../Approvals/MyDecisionsTrail';
import {
  isPastDated,
  pastDatedBlocksUser,
  pendingChangeDates,
  userMayApprovePastItems,
} from '../../utils/pastDatedApproval';
import { cn } from '../../lib/cn';

const TAB_WAITING = 'waiting';
const TAB_HISTORY = 'history';

const KIND_SALE = 'sale';
const KIND_COLLECTION = 'collection';

function ApprovalListRow({ title, subtitle, badge, amount, meta, selected, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex w-full items-center gap-3 border-b border-border/60 px-3 py-2.5 text-left transition-colors',
        'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        selected && 'bg-primary/5',
      )}
      data-testid="sale-approval-list-row"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="shrink-0 text-[10px]">
            {badge}
          </Badge>
          {meta ? (
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {meta}
            </Badge>
          ) : null}
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

function SaleReviewBody({ sale }) {
  const returned = saleNeedsSalespersonAction(sale);
  const managerComment = saleRejectionReason(sale);
  const saleDates = [sale.occurred_at || sale.created_at];
  const pastDated = isPastDated(...saleDates);
  const adminOnly = pastDatedBlocksUser(saleDates);
  const itemCount = saleDisplayItemCount(sale);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-sm">
        <Badge variant="outline">
          {Number(sale.amount_paid || 0) < Number(sale.total || 0)
            ? `Paid ${formatCurrency(sale.amount_paid || 0)} · debt remaining`
            : `Paid ${formatCurrency(sale.amount_paid || sale.total || 0)}`}
        </Badge>
        <span className="text-muted-foreground">
          {itemCount} line{itemCount === 1 ? '' : 's'}
          {sale.customer_name ? ` · ${sale.customer_name}` : ''}
        </span>
      </div>
      <ApprovalDetails details={sale.approval_details} />
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
      ) : null}
      {pastDated ? <PastDatedNotice dates={saleDates} blocked={adminOnly} /> : null}
    </div>
  );
}

function SaleReviewActions({ sale, onResolved, onClose }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const returned = saleNeedsSalespersonAction(sale);
  const saleDates = [sale.occurred_at || sale.created_at];
  const adminOnly = pastDatedBlocksUser(saleDates);

  const approve = async () => {
    setBusy(true);
    try {
      await salesAPI.complete(sale.id);
      toast.success(`Sale ${sale.sale_number} approved. Stock, books, and the receipt are live.`);
      onClose();
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
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.rejection_reason || 'Could not reject this sale');
    } finally {
      setBusy(false);
    }
  };

  if (returned || adminOnly) return null;

  return (
    <>
      <CenterScreenLoader open={busy} label="Processing approval…" />
      {showReject ? (
        <div className="w-full space-y-2">
          <Label htmlFor={`reject-${sale.id}`}>Reason</Label>
          <Input
            id={`reject-${sale.id}`}
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="Why should this sale not complete?"
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="destructive" onClick={reject} disabled={busy}>
              Confirm reject
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowReject(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={approve} disabled={busy}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <HelpHint actionKey="sale_complete" />
          <Button size="sm" variant="outline" onClick={() => setShowReject(true)} disabled={busy}>
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
        </div>
      )}
    </>
  );
}

function CollectionReviewBody({ change }) {
  const dates = pendingChangeDates(change);
  const pastDated = Boolean(change.past_dated) || isPastDated(...dates);
  const adminOnly = pastDated && !userMayApprovePastItems();

  return (
    <div className="space-y-4">
      {change.reason ? (
        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm">
          <span className="font-medium">Reason: </span>
          {change.reason}
        </div>
      ) : null}
      <ApprovalDetails details={change.details} />
      {pastDated ? <PastDatedNotice dates={dates} blocked={adminOnly} /> : null}
    </div>
  );
}

function CollectionReviewActions({ change, onResolved, onClose }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const dates = pendingChangeDates(change);
  const pastDated = Boolean(change.past_dated) || isPastDated(...dates);
  const adminOnly = pastDated && !userMayApprovePastItems();

  const approve = async () => {
    setBusy(true);
    try {
      await pendingChangesAPI.approve(change.id);
      toast.success(
        `Collection for ${change.entity_repr || 'customer'} approved. The wallet is updated.`,
      );
      onClose();
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
      onClose();
      onResolved();
      dispatchNavBadgesRefresh();
    } catch (err) {
      const data = err.response?.data;
      toast.error(data?.error || data?.rejection_reason || 'Could not reject this collection');
    } finally {
      setBusy(false);
    }
  };

  if (adminOnly) return null;

  return (
    <>
      <CenterScreenLoader open={busy} label="Processing approval…" />
      {showReject ? (
        <div className="w-full space-y-2">
          <Label htmlFor={`reject-collection-${change.id}`}>Reason</Label>
          <Input
            id={`reject-collection-${change.id}`}
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="Why should this collection not apply?"
          />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="destructive" onClick={reject} disabled={busy}>
              Confirm reject
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowReject(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={approve} disabled={busy}>
            {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
            Approve
          </Button>
          <HelpHint actionKey="debt_collection" />
          <Button size="sm" variant="outline" onClick={() => setShowReject(true)} disabled={busy}>
            <X className="mr-1 h-4 w-4" />
            Reject
          </Button>
        </div>
      )}
    </>
  );
}

function ListSection({ title, children }) {
  if (!children) return null;
  return (
    <section className="overflow-hidden rounded-lg border bg-card">
      <div className="border-b bg-muted/30 px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <div>{children}</div>
    </section>
  );
}

export default function SaleApprovalsPage() {
  const { permissions } = getStoredAuth();
  const allowed = userCanOpenSaleApprovals(permissions);
  const canSales = userCanApproveSales(permissions);
  const canCollections = userCanApproveDebtCollections(permissions);
  const [tab, setTab] = useState(TAB_WAITING);
  const [sales, setSales] = useState([]);
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const historyActionTypes = useMemo(() => {
    const types = [];
    if (canSales) types.push('sale_complete');
    if (canCollections) types.push('debt_collection');
    return types;
  }, [canSales, canCollections]);

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
            }),
        );
      } else {
        setSales([]);
      }
      if (canCollections) {
        tasks.push(
          pendingChangesAPI.pending(pendingDebtCollectionParams()).then((response) => {
            const data = response.data;
            setCollections(Array.isArray(data) ? data : data?.results || []);
          }),
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
    if (allowed && tab === TAB_WAITING) load();
  }, [allowed, load, tab]);

  const { waiting: waitingSales, returned: returnedSales } = useMemo(
    () => partitionSaleApprovalQueue(sales),
    [sales],
  );

  const openSale = useCallback(async (sale) => {
    const key = `sale-${sale.id}`;
    setSelected({ key, kind: KIND_SALE, data: sale });
    const hasDetails = Boolean(sale.approval_details?.sections?.length);
    if (hasDetails) return;
    try {
      const response = await salesAPI.get(sale.id);
      const detail = response.data || {};
      setSelected((current) => {
        if (!current || current.key !== key) return current;
        return {
          ...current,
          data: {
            ...sale,
            ...detail,
            approval_details: detail.approval_details || sale.approval_details,
          },
        };
      });
    } catch {
      /* list row still shows; checker can decide from summary */
    }
  }, []);

  const openCollection = useCallback((change) => {
    setSelected({
      key: `collection-${change.id}`,
      kind: KIND_COLLECTION,
      data: change,
    });
  }, []);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  const empty = saleApprovalsEmpty({ sales, collections });
  const selectedSale = selected?.kind === KIND_SALE ? selected.data : null;
  const selectedCollection = selected?.kind === KIND_COLLECTION ? selected.data : null;

  return (
    <PageShell>
      <PageHeader
        title="Approve sales"
        description="Review waiting sales and collections, or open Decisions for the full trail — filter by date and people."
        icon={CheckCircle2}
      />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Sale approvals views">
          <Button
            type="button"
            size="sm"
            variant={tab === TAB_WAITING ? 'default' : 'outline'}
            role="tab"
            aria-selected={tab === TAB_WAITING}
            onClick={() => setTab(TAB_WAITING)}
          >
            Waiting
          </Button>
          <Button
            type="button"
            size="sm"
            variant={tab === TAB_HISTORY ? 'default' : 'outline'}
            role="tab"
            aria-selected={tab === TAB_HISTORY}
            onClick={() => setTab(TAB_HISTORY)}
          >
            Decisions
          </Button>
        </div>
        {tab === TAB_WAITING ? (
          <Button type="button" variant="outline" onClick={load} disabled={loading}>
            Refresh list
          </Button>
        ) : null}
      </div>
      {tab === TAB_HISTORY ? (
        <MyDecisionsTrail
          actionTypes={historyActionTypes}
          emptyDescription="Approved and rejected sales and collections appear here. Filter by date or person."
        />
      ) : loading ? (
        <PageLoading />
      ) : empty ? (
        <EmptyState
          title="Nothing waiting"
          description="New cashier checkouts and salesperson collections will appear here."
        />
      ) : (
        <div className="space-y-4" data-testid="sale-approvals-list">
          {canSales && waitingSales.length > 0 ? (
            <ListSection title={`Cashier sales · ${waitingSales.length}`}>
              {waitingSales.map((sale) => (
                <ApprovalListRow
                  key={`sale-${sale.id}`}
                  title={sale.sale_number}
                  subtitle={`${sale.cashier_name || 'Cashier'} · ${formatDateTime(sale.occurred_at || sale.created_at)}`}
                  badge="Sale"
                  amount={Number(sale.total) || 0}
                  selected={selected?.key === `sale-${sale.id}`}
                  onOpen={() => openSale(sale)}
                />
              ))}
            </ListSection>
          ) : null}
          {canSales && returnedSales.length > 0 ? (
            <ListSection title={`Needs salesperson action · ${returnedSales.length}`}>
              {returnedSales.map((sale) => (
                <ApprovalListRow
                  key={`sale-${sale.id}`}
                  title={sale.sale_number}
                  subtitle={`${sale.cashier_name || 'Cashier'} · ${formatDateTime(sale.occurred_at || sale.created_at)}`}
                  badge="Sale"
                  meta="Returned"
                  amount={Number(sale.total) || 0}
                  selected={selected?.key === `sale-${sale.id}`}
                  onOpen={() => openSale(sale)}
                />
              ))}
            </ListSection>
          ) : null}
          {canCollections && collections.length > 0 ? (
            <ListSection title={`Debt collections · ${collections.length}`}>
              {collections.map((change) => (
                <ApprovalListRow
                  key={`collection-${change.id}`}
                  title={change.entity_repr || 'Customer'}
                  subtitle={`${change.made_by_username || 'Salesperson'} · ${formatDateTime(change.made_at)}`}
                  badge="Collection"
                  meta={collectionMethod(change)}
                  amount={collectionAmount(change)}
                  selected={selected?.key === `collection-${change.id}`}
                  onOpen={() => openCollection(change)}
                />
              ))}
            </ListSection>
          ) : null}
        </div>
      )}

      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent
          className="max-h-[90vh] max-w-2xl overflow-y-auto"
          description="Review this sale or collection, then approve or reject."
        >
          <DialogHeader>
            <DialogTitle className="pr-8">
              {selectedSale
                ? selectedSale.sale_number
                : selectedCollection
                  ? selectedCollection.entity_repr || 'Debt collection'
                  : 'Approval'}
            </DialogTitle>
            <DialogDescription>
              {selectedSale
                ? `${selectedSale.cashier_name || 'Cashier'} · ${formatDateTime(selectedSale.occurred_at || selectedSale.created_at)}`
                : selectedCollection
                  ? `${selectedCollection.made_by_username || 'Salesperson'} · ${formatDateTime(selectedCollection.made_at)}`
                  : 'Review and decide'}
            </DialogDescription>
          </DialogHeader>

          {selectedSale ? <SaleReviewBody sale={selectedSale} /> : null}
          {selectedCollection ? <CollectionReviewBody change={selectedCollection} /> : null}

          <DialogFooter className="flex-col items-stretch gap-2 sm:flex-col sm:space-x-0">
            {selectedSale ? (
              <SaleReviewActions
                key={`sale-actions-${selectedSale.id}`}
                sale={selectedSale}
                onResolved={load}
                onClose={() => setSelected(null)}
              />
            ) : null}
            {selectedCollection ? (
              <CollectionReviewActions
                key={`collection-actions-${selectedCollection.id}`}
                change={selectedCollection}
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
