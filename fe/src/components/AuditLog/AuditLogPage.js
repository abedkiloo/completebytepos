import React, { useCallback, useEffect, useState } from 'react';
import { ScrollText, Search, Loader2 } from 'lucide-react';
import { auditLogAPI } from '../../services/api';
import { PageShell, PageHeader, PageLoading } from '../page';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { userMayEditFinancialFieldsFromStorage } from '../../utils/roleAccess';
import { Navigate } from 'react-router-dom';

export default function AuditLogPage() {
  const allowed = userMayEditFinancialFieldsFromStorage();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [action, setAction] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
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
  }, [q, action]);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Audit log"
        description="Who changed prices, stock, sales, and sign-in activity."
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
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b border-border/60">
                      <td className="py-2 pr-3 whitespace-nowrap tabular-nums">
                        {formatDateTime(row.created_at)}
                      </td>
                      <td className="py-2 pr-3">{row.username_snapshot || '—'}</td>
                      <td className="py-2 pr-3">
                        <Badge variant="outline">{row.action}</Badge>
                      </td>
                      <td className="py-2 pr-3">{row.module || '—'}</td>
                      <td className="py-2 pr-3 max-w-md truncate" title={row.object_repr}>
                        {row.object_repr || row.object_type || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}
