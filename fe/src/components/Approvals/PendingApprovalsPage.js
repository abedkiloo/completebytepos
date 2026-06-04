import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { ClipboardCheck, Loader2, Check, X } from 'lucide-react';
import { pendingChangesAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading } from '../page';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { toast } from '../../utils/toast';
import { formatDateTime } from '../../utils/formatters';
import { userMayEditFinancialFieldsFromStorage } from '../../utils/roleAccess';
import { needsExtremePriceConfirm } from '../../utils/makerChecker';

function DiffBlock({ title, values }) {
  if (!values || !Object.keys(values).length) {
    return (
      <p className="text-xs text-muted-foreground">
        {title}: (none)
      </p>
    );
  }
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{title}</p>
      <pre className="max-h-40 overflow-auto rounded bg-muted p-2 text-xs">
        {JSON.stringify(values, null, 2)}
      </pre>
    </div>
  );
}

function PendingRow({ row, onResolved }) {
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [extremeConfirm, setExtremeConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const extremeRequired = needsExtremePriceConfirm(row);

  const approve = async () => {
    if (extremeRequired && !extremeConfirm) {
      toast.warning('Confirm the large price change before approving.');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.approve(row.id, {
        extreme_price_confirmed: extremeRequired ? extremeConfirm : false,
      });
      toast.success('Change approved and applied');
      onResolved();
    } catch (err) {
      const data = err.response?.data;
      const msg =
        (typeof data === 'object' && (data.error || Object.values(data).flat().join(', '))) ||
        data?.detail ||
        'Could not approve';
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!rejectReason.trim()) {
      toast.warning('Enter a rejection reason');
      return;
    }
    setBusy(true);
    try {
      await pendingChangesAPI.reject(row.id, { rejection_reason: rejectReason.trim() });
      toast.success('Change rejected');
      onResolved();
    } catch (err) {
      toast.error('Could not reject');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-l-4 border-l-amber-400">
      <CardContent className="space-y-3 pt-6">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{row.action_type}</Badge>
              {row.batch_id ? (
                <Badge variant="secondary" className="text-[10px]">
                  Batch
                </Badge>
              ) : null}
            </div>
            <p className="mt-1 font-medium">{row.entity_repr || row.entity_type}</p>
            <p className="text-xs text-muted-foreground">
              Proposed by {row.made_by_username || '—'} · {formatDateTime(row.made_at)}
            </p>
          </div>
        </div>
        <p className="text-sm">
          <span className="font-medium">Reason:</span> {row.reason}
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <DiffBlock title="Before (approved)" values={row.original_values} />
          <DiffBlock title="Proposed" values={row.proposed_values} />
        </div>
        {extremeRequired ? (
          <div className="rounded-md border border-amber-300 bg-amber-50/90 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/40">
            <p className="font-medium text-amber-900 dark:text-amber-100">
              Large price change (&gt;50% from approved price)
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Approved: {row.original_values?.price ?? '—'} → Proposed:{' '}
              {row.proposed_values?.price ?? '—'}
            </p>
            <label className="mt-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={extremeConfirm}
                onChange={(e) => setExtremeConfirm(e.target.checked)}
              />
              I confirm this price change is intentional
            </label>
          </div>
        ) : row.action_type === 'product_price' ? (
          <p className="text-xs text-muted-foreground">
            Price change is within the normal approval threshold.
          </p>
        ) : null}
        {showReject ? (
          <div className="space-y-2">
            <Label>Rejection reason</Label>
            <Input
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Why this change is not acceptable"
            />
            <div className="flex gap-2">
              <Button type="button" variant="destructive" size="sm" onClick={reject} disabled={busy}>
                Confirm reject
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
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function PendingApprovalsPage() {
  const allowed = userMayEditFinancialFieldsFromStorage();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await pendingChangesAPI.pending();
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch {
      toast.error('Could not load pending approvals');
      setRows([]);
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
        title="Pending approvals"
        description="Review and approve sensitive price, stock, and catalog changes before they go live."
        icon={ClipboardCheck}
      />
      <div className="mb-4 flex justify-end">
        <Button type="button" variant="outline" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>
      {loading ? (
        <PageLoading />
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            No changes waiting for approval.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
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
