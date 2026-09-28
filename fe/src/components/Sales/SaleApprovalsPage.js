import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Check, CheckCircle2, Loader2, X } from 'lucide-react';
import { salesAPI } from '../../services/api';
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
import { userCanApproveSales } from '../../utils/saleCompletionApproval';
import HelpHint from '../Shared/HelpHint';

function SaleApprovalRow({ sale, onResolved }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [busy, setBusy] = useState(false);
  const itemCount = saleDisplayItemCount(sale);

  const approve = async () => {
    setBusy(true);
    try {
      await salesAPI.complete(sale.id);
      toast.success(`Sale ${sale.sale_number} approved. The cashier can issue the receipt.`);
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
      toast.success(`Sale ${sale.sale_number} was cancelled.`);
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
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="font-semibold">{sale.sale_number}</p>
            <p className="text-sm text-muted-foreground">
              {sale.cashier_name || 'Cashier'} · {formatDateTime(sale.occurred_at || sale.created_at)}
            </p>
          </div>
          <div className="text-right">
            <p className="font-semibold">{formatCurrency(sale.total)}</p>
            <Badge variant="outline" className="capitalize">
              {sale.payment_method || 'cash'}
            </Badge>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {itemCount} line{itemCount === 1 ? '' : 's'}
          {sale.customer_name ? ` · ${sale.customer_name}` : ''}
        </p>
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
      </CardContent>
    </Card>
  );
}

export default function SaleApprovalsPage() {
  const { permissions } = getStoredAuth();
  const allowed = userCanApproveSales(permissions);
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await salesAPI.list({ status: 'pending_approval', page_size: 100 });
      const data = response.data;
      setSales(data.results || (Array.isArray(data) ? data : []));
    } catch (error) {
      setSales([]);
      toast.error('Could not load sales waiting for approval');
    } finally {
      setLoading(false);
    }
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
        title="Approve sales"
        description="Cashiers can ring up a sale, but stock and receipts wait until you approve."
        icon={CheckCircle2}
      >
        <Button type="button" variant="outline" onClick={load} disabled={loading}>
          Refresh list
        </Button>
      </PageHeader>
      {loading ? (
        <PageLoading />
      ) : sales.length === 0 ? (
        <EmptyState title="No sales waiting" description="New cashier checkouts will appear here." />
      ) : (
        <div className="space-y-3">
          {sales.map((sale) => (
            <SaleApprovalRow key={sale.id} sale={sale} onResolved={load} />
          ))}
        </div>
      )}
    </PageShell>
  );
}
