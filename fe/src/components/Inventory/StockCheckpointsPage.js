import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Lock, Plus, Search } from 'lucide-react';

import { inventoryAPI, productsAPI } from '../../services/api';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
} from '../page';

function statusBadge(status) {
  if (status === 'open') return <Badge variant="warning">Open</Badge>;
  if (status === 'closed') return <Badge variant="success">Closed</Badge>;
  return <Badge variant="secondary">{status}</Badge>;
}

export default function StockCheckpointsPage() {
  const { permissions } = getStoredAuth();
  const allowed = hasPermission(permissions, 'inventory', 'manage');
  const { settings: inventorySettings } = useModuleSettings('inventory');
  const defaultBlockSales = inventorySettings?.block_sales_during_checkpoint !== false;

  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [countDrafts, setCountDrafts] = useState({});
  const [busy, setBusy] = useState(false);

  const [showOpen, setShowOpen] = useState(false);
  const [openTitle, setOpenTitle] = useState('');
  const [openNotes, setOpenNotes] = useState('');
  const [includeAll, setIncludeAll] = useState(true);
  const [blockSales, setBlockSales] = useState(true);
  const [productQuery, setProductQuery] = useState('');
  const [productHits, setProductHits] = useState([]);
  const [pickedIds, setPickedIds] = useState([]);

  useEffect(() => {
    if (showOpen) {
      setBlockSales(defaultBlockSales);
    }
  }, [showOpen, defaultBlockSales]);

  const loadList = useCallback(async () => {
    if (!allowed) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await inventoryAPI.checkpoints();
      setRows(res.data?.results || res.data || []);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not load checkpoints');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [allowed]);

  const loadDetail = useCallback(async (id) => {
    if (!id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const res = await inventoryAPI.checkpoint(id);
      setDetail(res.data);
      const drafts = {};
      for (const line of res.data?.lines || []) {
        drafts[line.id] =
          line.counted_qty != null ? String(line.counted_qty) : String(line.system_qty_at_open ?? 0);
      }
      setCountDrafts(drafts);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not load checkpoint');
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (!showOpen || includeAll || !productQuery.trim()) {
      setProductHits([]);
      return undefined;
    }
    const t = setTimeout(async () => {
      try {
        const res = await productsAPI.list({
          search: productQuery.trim(),
          page_size: 20,
          track_stock: true,
        });
        setProductHits(res.data?.results || res.data || []);
      } catch {
        setProductHits([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [showOpen, includeAll, productQuery]);

  const handleOpen = async () => {
    if (!openTitle.trim()) {
      toast.error('Enter a checkpoint title');
      return;
    }
    setBusy(true);
    try {
      const payload = {
        title: openTitle.trim(),
        notes: openNotes.trim(),
        include_all_tracked: includeAll,
        product_ids: includeAll ? [] : pickedIds,
        block_sales: blockSales,
      };
      const res = await inventoryAPI.openCheckpoint(payload);
      toast.success(
        blockSales
          ? 'Checkpoint opened — count stock at hand before selling those products'
          : 'Checkpoint opened — sales continue while you count'
      );
      setShowOpen(false);
      setOpenTitle('');
      setOpenNotes('');
      setPickedIds([]);
      await loadList();
      setSelectedId(res.data?.id);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not open checkpoint');
    } finally {
      setBusy(false);
    }
  };

  const handleCount = async (line) => {
    const raw = countDrafts[line.id];
    const qty = parseInt(String(raw).trim(), 10);
    if (Number.isNaN(qty) || qty < 0) {
      toast.error('Enter a valid stock-at-hand quantity');
      return;
    }
    setBusy(true);
    try {
      await inventoryAPI.countCheckpointLine(selectedId, line.id, { counted_qty: qty });
      toast.success(`Counted ${line.product_name}`);
      await loadDetail(selectedId);
      await loadList();
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not save count');
    } finally {
      setBusy(false);
    }
  };

  const handleClose = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      await inventoryAPI.closeCheckpoint(selectedId);
      toast.success('Checkpoint closed — reporting baseline set');
      await loadList();
      await loadDetail(selectedId);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not close checkpoint');
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedId) return;
    if (!window.confirm('Cancel this checkpoint? Sell blocks lift without changing stock.')) {
      return;
    }
    setBusy(true);
    try {
      await inventoryAPI.cancelCheckpoint(selectedId);
      toast.success('Checkpoint cancelled');
      await loadList();
      await loadDetail(selectedId);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Could not cancel checkpoint');
    } finally {
      setBusy(false);
    }
  };

  if (!allowed) {
    return (
      <PageShell>
        <PageHeader
          title="Stock checkpoints"
          description="Freeze selected products until stock at hand is counted."
        />
        <EmptyState
          icon={Lock}
          title="Checkpoints are restricted"
          description="Only roles with inventory manage can open and count stock checkpoints."
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        title="Stock checkpoints"
        description="Open a count, optionally stop sales until stock at hand is set, then close to start a new reporting journey."
      >
        <Button type="button" onClick={() => setShowOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          Open checkpoint
        </Button>
      </PageHeader>
      <p className="mb-3 text-xs text-muted-foreground">
        Default for new stock takes:{' '}
        <span className="font-medium text-foreground">
          {defaultBlockSales ? 'stop sales until counted' : 'allow sales while counting'}
        </span>
        . Change under Module Settings → Inventory → “Block sales during stock take”.
      </p>

      {loading ? (
        <PageLoading rows={6} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <div className="space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Checkpoints
            </h2>
            {rows.length === 0 ? (
              <EmptyState
                icon={ClipboardCheck}
                title="No checkpoints yet"
                description="Open one to count stock at hand and align inventory with accounting."
              />
            ) : (
              <div className="space-y-2">
                {rows.map((row) => (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => setSelectedId(row.id)}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selectedId === row.id
                        ? 'border-primary bg-primary/5'
                        : 'hover:bg-muted/40'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{row.title}</span>
                      <span className="flex items-center gap-1.5">
                        {row.status === 'open' && row.block_sales === false ? (
                          <Badge variant="secondary">Sales open</Badge>
                        ) : null}
                        {row.status === 'open' && row.block_sales !== false ? (
                          <Badge variant="warning">Sales blocked</Badge>
                        ) : null}
                        {statusBadge(row.status)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Opened {formatDateTime(row.opened_at)}
                      {row.closed_at ? ` · Closed ${formatDateTime(row.closed_at)}` : ''}
                    </div>
                    <div className="mt-1 text-xs">
                      {row.counted_line_count || 0}/{row.line_count || 0} counted
                      {row.pending_line_count
                        ? ` · ${row.pending_line_count} pending`
                        : ''}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="min-w-0 rounded-lg border p-4">
            {!selectedId ? (
              <p className="text-sm text-muted-foreground">Select a checkpoint to count lines.</p>
            ) : detailLoading || !detail ? (
              <PageLoading rows={4} />
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-bold">{detail.title}</h2>
                      {statusBadge(detail.status)}
                      {detail.status === 'open' ? (
                        detail.block_sales !== false ? (
                          <Badge variant="warning">Sales blocked until counted</Badge>
                        ) : (
                          <Badge variant="secondary">Sales continue while counting</Badge>
                        )
                      ) : null}
                    </div>
                    {detail.notes ? (
                      <p className="mt-1 text-sm text-muted-foreground">{detail.notes}</p>
                    ) : null}
                    {detail.status === 'closed' && detail.inventory_value_after != null ? (
                      <p className="mt-1 text-sm">
                        Inventory value after count:{' '}
                        <strong>{formatCurrency(detail.inventory_value_after)}</strong>
                      </p>
                    ) : null}
                  </div>
                  {detail.status === 'open' ? (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        disabled={busy || (detail.pending_line_count || 0) > 0}
                        onClick={handleClose}
                      >
                        Close checkpoint
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={busy}
                        onClick={handleCancel}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : null}
                </div>

                <DataTable>
                  <DataTableHeader>
                    <DataTableHead>Product</DataTableHead>
                    <DataTableHead align="right">Was</DataTableHead>
                    <DataTableHead align="right">Stock at hand</DataTableHead>
                    <DataTableHead align="right">Action</DataTableHead>
                  </DataTableHeader>
                  <DataTableBody>
                    {(detail.lines || []).map((line) => (
                      <DataTableRow key={line.id}>
                        <DataTableCell>
                          <div className="font-medium">{line.product_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {[line.product_sku, line.variant_label].filter(Boolean).join(' · ')}
                          </div>
                        </DataTableCell>
                        <DataTableCell align="right">{line.system_qty_at_open}</DataTableCell>
                        <DataTableCell align="right">
                          {line.status === 'counted' ? (
                            line.counted_qty
                          ) : (
                            <Input
                              type="number"
                              min={0}
                              className="ml-auto h-9 w-24 text-right"
                              value={countDrafts[line.id] ?? ''}
                              disabled={busy || detail.status !== 'open'}
                              onChange={(e) =>
                                setCountDrafts((prev) => ({
                                  ...prev,
                                  [line.id]: e.target.value,
                                }))
                              }
                            />
                          )}
                        </DataTableCell>
                        <DataTableCell align="right">
                          {line.status === 'counted' ? (
                            <Badge variant="success">Counted</Badge>
                          ) : detail.status === 'open' ? (
                            <Button
                              type="button"
                              size="sm"
                              disabled={busy}
                              onClick={() => handleCount(line)}
                            >
                              Save count
                            </Button>
                          ) : (
                            <Badge variant="secondary">Pending</Badge>
                          )}
                        </DataTableCell>
                      </DataTableRow>
                    ))}
                  </DataTableBody>
                </DataTable>
              </>
            )}
          </div>
        </div>
      )}

      <Dialog open={showOpen} onOpenChange={setShowOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Open stock checkpoint</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <label className="text-sm font-medium">
              Title
              <Input
                className="mt-1"
                value={openTitle}
                onChange={(e) => setOpenTitle(e.target.value)}
                placeholder="e.g. March stocktake"
              />
            </label>
            <label className="text-sm font-medium">
              Notes (optional)
              <Input
                className="mt-1"
                value={openNotes}
                onChange={(e) => setOpenNotes(e.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeAll}
                onChange={(e) => setIncludeAll(e.target.checked)}
              />
              Include all tracked products
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={blockSales}
                onChange={(e) => setBlockSales(e.target.checked)}
              />
              <span>
                Stop sales on included products until counted
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  Uncheck to count stock while POS keeps selling. Default comes from Module Settings.
                </span>
              </span>
            </label>
            {!includeAll ? (
              <div>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    value={productQuery}
                    onChange={(e) => setProductQuery(e.target.value)}
                    placeholder="Search products to include…"
                  />
                </div>
                <div className="mt-2 max-h-40 overflow-y-auto rounded border">
                  {productHits.map((p) => {
                    const checked = pickedIds.includes(p.id);
                    return (
                      <label
                        key={p.id}
                        className="flex cursor-pointer items-center gap-2 border-b px-3 py-2 text-sm last:border-0"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() =>
                            setPickedIds((prev) =>
                              checked ? prev.filter((id) => id !== p.id) : [...prev, p.id]
                            )
                          }
                        />
                        <span>{p.name}</span>
                      </label>
                    );
                  })}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {pickedIds.length} product{pickedIds.length === 1 ? '' : 's'} selected
                </p>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setShowOpen(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={busy} onClick={handleOpen}>
              {blockSales ? 'Open & block sales' : 'Open (sales continue)'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
