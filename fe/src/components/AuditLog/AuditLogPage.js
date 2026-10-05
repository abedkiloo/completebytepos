import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollText, Search, Loader2 } from 'lucide-react';
import { auditLogAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading } from '../page';
import { ListSortBar } from '../page/ListSortBar';
import { useListOrdering } from '../../hooks/useListOrdering';
import { withListOrdering } from '../../utils/listOrdering';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { userMayEditFinancialFieldsFromStorage } from '../../utils/roleAccess';
import { Navigate } from 'react-router-dom';
import { cn } from '../../lib/cn';

const ACTION_LABELS = {
  create: 'Created',
  update: 'Updated',
  delete: 'Deleted',
  login: 'Signed in',
  logout: 'Signed out',
  login_failed: 'Failed sign-in',
  permission_denied: 'Permission denied',
  checkout: 'Checkout',
  holding_save: 'Saved holding',
  stock_adjust: 'Stock adjust',
  stock_purchase: 'Stock purchase',
  approve: 'Approved',
  reject: 'Rejected',
  pending_submit: 'Submitted for approval',
  pending_approve: 'Approved change',
  pending_reject: 'Rejected change',
};

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function humanFieldName(key) {
  return String(key || '')
    .replace(/^__|__$/g, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Flatten audit `changes` into readable rows for list + detail. */
export function parseAuditChanges(changes) {
  if (!changes || typeof changes !== 'object' || Array.isArray(changes)) {
    return { kind: 'empty', rows: [] };
  }
  if (changes.__created__ && typeof changes.__created__ === 'object') {
    return {
      kind: 'created',
      rows: Object.entries(changes.__created__).map(([field, value]) => ({
        field,
        label: humanFieldName(field),
        from: null,
        to: value,
      })),
    };
  }
  if (changes.__deleted__ && typeof changes.__deleted__ === 'object') {
    return {
      kind: 'deleted',
      rows: Object.entries(changes.__deleted__).map(([field, value]) => ({
        field,
        label: humanFieldName(field),
        from: value,
        to: null,
      })),
    };
  }

  const rows = [];
  Object.entries(changes).forEach(([field, value]) => {
    if (value && typeof value === 'object' && ('from' in value || 'to' in value)) {
      rows.push({
        field,
        label: humanFieldName(field),
        from: value.from,
        to: value.to,
      });
    } else {
      rows.push({
        field,
        label: humanFieldName(field),
        from: null,
        to: value,
      });
    }
  });
  return { kind: rows.length ? 'diff' : 'empty', rows };
}

export function summarizeAuditChanges(changes, maxItems = 3) {
  const parsed = parseAuditChanges(changes);
  if (!parsed.rows.length) return 'No values recorded';
  const parts = parsed.rows.slice(0, maxItems).map((row) => {
    if (row.from != null && row.to != null) {
      return `${row.label}: ${formatValue(row.from)} → ${formatValue(row.to)}`;
    }
    return `${row.label}: ${formatValue(row.to ?? row.from)}`;
  });
  const extra = parsed.rows.length - maxItems;
  return extra > 0 ? `${parts.join(' · ')} · +${extra} more` : parts.join(' · ');
}

function actionLabel(action) {
  if (!action) return '—';
  return ACTION_LABELS[action] || humanFieldName(action);
}

function ChangesTable({ changes }) {
  const parsed = useMemo(() => parseAuditChanges(changes), [changes]);
  if (!parsed.rows.length) {
    return <p className="text-sm text-muted-foreground">No entered values were stored for this event.</p>;
  }
  const showFrom = parsed.kind === 'diff' || parsed.kind === 'deleted';
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/40 text-left text-muted-foreground">
            <th className="px-3 py-2 font-medium">Field</th>
            {showFrom ? <th className="px-3 py-2 font-medium">Before</th> : null}
            <th className="px-3 py-2 font-medium">
              {parsed.kind === 'created' ? 'Entered value' : parsed.kind === 'deleted' ? 'Removed value' : 'After / value'}
            </th>
          </tr>
        </thead>
        <tbody>
          {parsed.rows.map((row) => (
            <tr key={row.field} className="border-b border-border/60 align-top">
              <td className="px-3 py-2 font-medium text-foreground">{row.label}</td>
              {showFrom ? (
                <td className="px-3 py-2 whitespace-pre-wrap break-words text-muted-foreground">
                  {formatValue(row.from)}
                </td>
              ) : null}
              <td className="px-3 py-2 whitespace-pre-wrap break-words tabular-nums">
                {formatValue(row.to ?? row.from)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AuditLogPage() {
  const allowed = userMayEditFinancialFieldsFromStorage();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [action, setAction] = useState('');
  const { ordering, setOrdering } = useListOrdering();
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = withListOrdering({}, ordering);
      if (q.trim()) params.q = q.trim();
      if (action) params.action = action;
      const res = await auditLogAPI.list(params);
      const data = res.data?.results ?? res.data ?? [];
      setRows(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Could not load audit log');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, action, ordering]);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return undefined;
    }
    let cancelled = false;
    const fromList = rows.find((r) => r.id === selectedId);
    if (fromList) setDetail(fromList);
    setDetailLoading(true);
    auditLogAPI
      .get(selectedId)
      .then((res) => {
        if (!cancelled) setDetail(res.data);
      })
      .catch(() => {
        if (!cancelled && !fromList) {
          toast.error('Could not load audit details');
          setSelectedId(null);
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, rows]);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Audit log"
        description="Who changed prices, stock, sales, and sign-in activity. Click a row to see what they entered."
        icon={ScrollText}
      />
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="Search user, object, path…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <select
              className="h-9 rounded-md border px-2 text-sm"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              <option value="">All actions</option>
              <option value="login">Login</option>
              <option value="logout">Logout</option>
              <option value="checkout">Checkout</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="stock_adjust">Stock adjust</option>
            </select>
            <ListSortBar value={ordering} onChange={setOrdering} />
            <Button type="button" onClick={load}>
              Apply
            </Button>
          </div>
          {loading ? (
            <PageLoading label="Loading audit entries…" />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No audit entries match these filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-3">When</th>
                    <th className="py-2 pr-3">User</th>
                    <th className="py-2 pr-3">Action</th>
                    <th className="py-2 pr-3">Module</th>
                    <th className="py-2 pr-3">Object</th>
                    <th className="py-2 pr-3">Values</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className={cn(
                        'cursor-pointer border-b border-border/60 transition-colors hover:bg-muted/50',
                        selectedId === row.id && 'bg-primary/5'
                      )}
                      onClick={() => setSelectedId(row.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedId(row.id);
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-label={`Open audit detail for ${actionLabel(row.action)}`}
                    >
                      <td className="py-2 pr-3 whitespace-nowrap tabular-nums">
                        {formatDateTime(row.created_at)}
                      </td>
                      <td className="py-2 pr-3">{row.username_snapshot || '—'}</td>
                      <td className="py-2 pr-3">
                        <Badge variant="outline">{actionLabel(row.action)}</Badge>
                      </td>
                      <td className="py-2 pr-3">{row.module || '—'}</td>
                      <td className="py-2 pr-3 max-w-[12rem] truncate" title={row.object_repr}>
                        {row.object_repr || row.object_type || '—'}
                      </td>
                      <td
                        className="py-2 pr-3 max-w-[20rem] truncate text-muted-foreground"
                        title={summarizeAuditChanges(row.changes)}
                      >
                        {summarizeAuditChanges(row.changes)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(selectedId)} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DialogContent
          className="max-h-[90vh] max-w-2xl overflow-y-auto"
          description="Full audit trail entry showing what was entered in the system."
        >
          <DialogHeader>
            <DialogTitle>Audit trail details</DialogTitle>
            <DialogDescription>
              What changed, who did it, and the values recorded in the system.
            </DialogDescription>
          </DialogHeader>
          {detailLoading && !detail ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading details…
            </div>
          ) : detail ? (
            <div className="space-y-4">
              <dl className="grid gap-3 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">When</dt>
                  <dd className="text-sm tabular-nums">{formatDateTime(detail.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">User</dt>
                  <dd className="text-sm">{detail.username_snapshot || detail.user_username || '—'}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">Action</dt>
                  <dd className="text-sm">
                    <Badge variant="outline">{actionLabel(detail.action)}</Badge>
                    <span className="ml-2 text-xs text-muted-foreground">({detail.action})</span>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">Module</dt>
                  <dd className="text-sm">{detail.module || '—'}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-xs font-medium text-muted-foreground">Object</dt>
                  <dd className="text-sm break-words">
                    {detail.object_repr || '—'}
                    {detail.object_type ? (
                      <span className="ml-2 text-xs text-muted-foreground">
                        {detail.object_type}
                        {detail.object_id ? ` #${detail.object_id}` : ''}
                      </span>
                    ) : null}
                  </dd>
                </div>
                {(detail.path || detail.method) && (
                  <div className="sm:col-span-2">
                    <dt className="text-xs font-medium text-muted-foreground">Request</dt>
                    <dd className="text-sm font-mono text-xs break-all">
                      {[detail.method, detail.path].filter(Boolean).join(' ')}
                    </dd>
                  </div>
                )}
                {detail.ip_address ? (
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">IP</dt>
                    <dd className="text-sm tabular-nums">{detail.ip_address}</dd>
                  </div>
                ) : null}
              </dl>

              <div>
                <h3 className="mb-2 text-sm font-semibold">What they entered</h3>
                <ChangesTable changes={detail.changes} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No detail available.</p>
          )}
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
