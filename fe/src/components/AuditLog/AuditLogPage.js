import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollText, Search, Loader2 } from 'lucide-react';
import { auditLogAPI, usersAPI } from '../../services/api';
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
  stock_transfer: 'Stock transfer',
  stock_undo: 'Stock undo',
  approve: 'Approved',
  reject: 'Rejected',
  pending_submit: 'Submitted for approval',
  pending_approve: 'Approved change',
  pending_reject: 'Rejected change',
  refund: 'Refund',
  rollback: 'Rollback',
};

const MODULE_OPTIONS = [
  { value: '', label: 'All modules' },
  { value: 'sales', label: 'Sales / POS' },
  { value: 'products', label: 'Products' },
  { value: 'inventory', label: 'Inventory' },
  { value: 'customers', label: 'Customers' },
  { value: 'users', label: 'Users' },
  { value: 'roles', label: 'Roles' },
  { value: 'approvals', label: 'Approvals' },
  { value: 'expenses', label: 'Expenses' },
  { value: 'income', label: 'Income' },
  { value: 'bankaccounts', label: 'Bank accounts' },
  { value: 'transfers', label: 'Money transfers' },
  { value: 'accounting', label: 'Accounting' },
  { value: 'payroll', label: 'Payroll' },
  { value: 'employees', label: 'Employees' },
  { value: 'appraisals', label: 'Target delivery' },
  { value: 'suppliers', label: 'Suppliers' },
  { value: 'agents', label: 'Field / sites' },
  { value: 'dispatch', label: 'Dispatch' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'payments', label: 'Payments' },
  { value: 'messaging', label: 'Messaging' },
  { value: 'daily_notes', label: 'Daily notes' },
  { value: 'settings', label: 'Settings' },
  { value: 'module_settings', label: 'Module settings' },
  { value: 'website', label: 'Website / CMS' },
];

function todayIsoDate() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function humanModuleName(value) {
  const hit = MODULE_OPTIONS.find((o) => o.value === value);
  if (hit) return hit.label;
  return humanFieldName(value);
}

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
  const [module, setModule] = useState('');
  const [userId, setUserId] = useState('');
  const [dateFrom, setDateFrom] = useState(todayIsoDate);
  const [dateTo, setDateTo] = useState(todayIsoDate);
  const [timeFrom, setTimeFrom] = useState('');
  const [timeTo, setTimeTo] = useState('');
  const [users, setUsers] = useState([]);
  const [facetModules, setFacetModules] = useState([]);
  const [facetActions, setFacetActions] = useState([]);
  const { ordering, setOrdering } = useListOrdering();
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const moduleOptions = useMemo(() => {
    const known = new Map(MODULE_OPTIONS.map((o) => [o.value, o]));
    for (const m of facetModules) {
      if (m && !known.has(m)) {
        known.set(m, { value: m, label: humanModuleName(m) });
      }
    }
    return Array.from(known.values());
  }, [facetModules]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = withListOrdering({}, ordering);
      if (q.trim()) params.q = q.trim();
      if (action) params.action = action;
      if (module) params.module = module;
      if (userId) params.user = userId;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (timeFrom) params.time_from = timeFrom;
      if (timeTo) params.time_to = timeTo;
      const res = await auditLogAPI.list(params);
      const data = res.data?.results ?? res.data ?? [];
      setRows(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Could not load audit log');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, action, module, userId, dateFrom, dateTo, timeFrom, timeTo, ordering]);

  useEffect(() => {
    if (!allowed) return undefined;
    let cancelled = false;
    usersAPI
      .list({ page_size: 200 })
      .then((res) => {
        if (cancelled) return;
        const data = res.data?.results ?? res.data ?? [];
        setUsers(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      });
    auditLogAPI
      .facets()
      .then((res) => {
        if (cancelled) return;
        setFacetModules(Array.isArray(res.data?.modules) ? res.data.modules : []);
        setFacetActions(Array.isArray(res.data?.actions) ? res.data.actions : []);
      })
      .catch(() => {
        if (!cancelled) {
          setFacetModules([]);
          setFacetActions([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);

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
        description="Everything any user does in the system — every module. Filter by day, time, user, module, or action. Click a row for before/after values."
        icon={ScrollText}
      />
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="Search user, object, path, module…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <label className="flex items-center gap-1 text-sm text-muted-foreground">
              <span className="sr-only">From date</span>
              <Input
                type="date"
                aria-label="From date"
                className="h-9 w-auto"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </label>
            <Input
              type="time"
              aria-label="From time"
              className="h-9 w-auto"
              value={timeFrom}
              onChange={(e) => setTimeFrom(e.target.value)}
            />
            <label className="flex items-center gap-1 text-sm text-muted-foreground">
              <span className="sr-only">To date</span>
              <Input
                type="date"
                aria-label="To date"
                className="h-9 w-auto"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </label>
            <Input
              type="time"
              aria-label="To time"
              className="h-9 w-auto"
              value={timeTo}
              onChange={(e) => setTimeTo(e.target.value)}
            />
            <select
              className="h-9 rounded-md border px-2 text-sm"
              aria-label="Filter by user"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            >
              <option value="">All users</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username || u.email || `User ${u.id}`}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border px-2 text-sm"
              aria-label="Filter by module"
              value={module}
              onChange={(e) => setModule(e.target.value)}
            >
              {moduleOptions.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border px-2 text-sm"
              aria-label="Filter by action"
              value={action}
              onChange={(e) => setAction(e.target.value)}
            >
              <option value="">All actions</option>
              <option value="login">Login</option>
              <option value="logout">Logout</option>
              <option value="checkout">Checkout</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
              <option value="assign_role">Assign role</option>
              <option value="change_password">Change password</option>
              <option value="stock_adjust">Stock adjust</option>
              <option value="stock_purchase">Stock purchase</option>
              <option value="stock_transfer">Stock transfer</option>
              <option value="refund">Refund</option>
              <option value="rollback">Rollback</option>
              <option value="pending_submit">Submitted for approval</option>
              <option value="pending_approve">Approved change</option>
              <option value="pending_reject">Rejected change</option>
              {facetActions
                .filter(
                  (a) =>
                    ![
                      'login',
                      'logout',
                      'checkout',
                      'create',
                      'update',
                      'delete',
                      'assign_role',
                      'change_password',
                      'stock_adjust',
                      'stock_purchase',
                      'stock_transfer',
                      'refund',
                      'rollback',
                      'pending_submit',
                      'pending_approve',
                      'pending_reject',
                    ].includes(a)
                )
                .map((a) => (
                  <option key={a} value={a}>
                    {actionLabel(a)}
                  </option>
                ))}
            </select>
            <ListSortBar value={ordering} onChange={setOrdering} />
            <Button type="button" onClick={load}>
              Apply
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setDateFrom('');
                setDateTo('');
                setTimeFrom('');
                setTimeTo('');
                setUserId('');
                setModule('');
                setAction('');
                setQ('');
              }}
            >
              All time
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const today = todayIsoDate();
                setDateFrom(today);
                setDateTo(today);
                setTimeFrom('');
                setTimeTo('');
              }}
            >
              Today
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
