import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ClipboardCheck, Lock, Plus, Search } from 'lucide-react';

import { inventoryAPI, productsAPI } from '../../services/api';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { clearFormBanner, reportFormError } from '../../utils/formFeedback';
import {
  buildCloseCheckpointSummary,
  buildPendingCountPayload,
  hasAnySavablePendingDraft,
  isCountDraftChanged,
  isCountDraftSavable,
  parseCountDraft,
  sortCheckpointLines,
  systemQtyAtOpen,
} from '../../utils/checkpointCountDrafts';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import FormBanner from '../form/FormBanner';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
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
  const [formBanner, setFormBanner] = useState(null);
  const [openFormBanner, setOpenFormBanner] = useState(null);
  const linesTopRef = useRef(null);

  const [showOpen, setShowOpen] = useState(false);
  const [openTitle, setOpenTitle] = useState('');
  const [openNotes, setOpenNotes] = useState('');
  const [includeAll, setIncludeAll] = useState(true);
  const [blockSales, setBlockSales] = useState(true);
  const [productQuery, setProductQuery] = useState('');
  const [productHits, setProductHits] = useState([]);
  const [pickedIds, setPickedIds] = useState([]);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [closeSummary, setCloseSummary] = useState(null);

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
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not load checkpoints');
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
      clearFormBanner(setFormBanner);
      const drafts = {};
      for (const line of res.data?.lines || []) {
        drafts[line.id] =
          line.counted_qty != null ? String(line.counted_qty) : String(line.system_qty_at_open ?? 0);
      }
      setCountDrafts(drafts);
    } catch (err) {
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not load checkpoint');
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadDetail(selectedId);
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
      reportFormError(setOpenFormBanner, 'Enter a checkpoint title');
      return;
    }
    setBusy(true);
    clearFormBanner(setOpenFormBanner);
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
      clearFormBanner(setOpenFormBanner);
      await loadList();
      setSelectedId(res.data?.id);
    } catch (err) {
      reportFormError(setOpenFormBanner, err.response?.data?.error || 'Could not open checkpoint');
    } finally {
      setBusy(false);
    }
  };

  const pendingLines = (detail?.lines || []).filter((line) => line.status !== 'counted');
  const sortedLines = sortCheckpointLines(detail?.lines || []);
  const canSavePending = hasAnySavablePendingDraft(pendingLines, countDrafts);

  const scrollLinesToTop = () => {
    try {
      linesTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch {
      /* ignore */
    }
  };

  const handleCount = async (line) => {
    const raw = countDrafts[line.id];
    const correcting = line.status === 'counted';
    if (!isCountDraftSavable(line, raw)) {
      reportFormError(
        setFormBanner,
        correcting
          ? 'Change the quantity to correct this count.'
          : 'Enter a valid stock-at-hand quantity'
      );
      return;
    }
    const qty = parseCountDraft(raw);
    const unchanged = !correcting && qty === systemQtyAtOpen(line);
    setBusy(true);
    try {
      await inventoryAPI.countCheckpointLine(selectedId, line.id, { counted_qty: qty });
      clearFormBanner(setFormBanner);
      toast.success(
        correcting
          ? `Corrected ${line.product_name} to ${qty}`
          : unchanged
            ? `Confirmed ${line.product_name} (no stock change)`
            : `Counted ${line.product_name}`
      );
      await loadDetail(selectedId);
      await loadList();
      if (!correcting) {
        requestAnimationFrame(scrollLinesToTop);
      }
    } catch (err) {
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not save count');
    } finally {
      setBusy(false);
    }
  };

  const handleCountAll = async () => {
    if (!selectedId || !detail || detail.status !== 'open') return;
    if (pendingLines.length === 0) {
      reportFormError(setFormBanner, 'All lines are already counted');
      return;
    }
    const { payload } = buildPendingCountPayload(pendingLines, countDrafts);
    if (payload.length === 0) {
      reportFormError(setFormBanner, 'Enter a valid stock-at-hand quantity for at least one line.');
      return;
    }
    setBusy(true);
    try {
      const res = await inventoryAPI.countCheckpointAll(selectedId, { lines: payload });
      const n = res.data?.counted ?? payload.length;
      clearFormBanner(setFormBanner);
      toast.success(`Confirmed ${n} count${n === 1 ? '' : 's'}`);
      await loadDetail(selectedId);
      await loadList();
    } catch (err) {
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not save counts');
    } finally {
      setBusy(false);
    }
  };

  const openCloseConfirm = () => {
    if (!detail || detail.status !== 'open') return;
    if ((detail.pending_line_count || 0) > 0) {
      reportFormError(
        setFormBanner,
        'Confirm every line first (same as system qty is fine — use Confirm / Confirm all).'
      );
      return;
    }
    setCloseSummary(buildCloseCheckpointSummary(detail.lines || []));
    setShowCloseConfirm(true);
  };

  const handleCloseConfirm = async () => {
    if (!selectedId) return;
    setBusy(true);
    try {
      await inventoryAPI.closeCheckpoint(selectedId);
      clearFormBanner(setFormBanner);
      setShowCloseConfirm(false);
      setCloseSummary(null);
      toast.success('Checkpoint closed — reporting baseline set');
      await loadList();
      await loadDetail(selectedId);
    } catch (err) {
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not close checkpoint');
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
      clearFormBanner(setFormBanner);
      toast.success('Checkpoint cancelled');
      await loadList();
      await loadDetail(selectedId);
    } catch (err) {
      reportFormError(setFormBanner, err.response?.data?.error || 'Could not cancel checkpoint');
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
      <FormBanner
        message={formBanner?.message}
        type={formBanner?.type || 'error'}
        onDismiss={() => clearFormBanner(setFormBanner)}
      />

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
                        disabled={busy || (pendingLines.length > 0 && !canSavePending)}
                        onClick={handleCountAll}
                        title={
                          pendingLines.length === 0
                            ? 'All lines are already counted'
                            : canSavePending
                              ? 'Confirm all pending lines (including unchanged stock)'
                              : 'Enter a valid quantity on pending lines'
                        }
                      >
                        Confirm all
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={busy}
                        onClick={openCloseConfirm}
                        title={
                          (detail.pending_line_count || 0) > 0
                            ? 'Confirm every line before closing'
                            : 'Review summary and close'
                        }
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
                {detail.status === 'open' ? (
                  <p className="mb-3 text-xs text-muted-foreground">
                    Still to count stays on top. Same as system? Click Confirm — no stock change.
                    Changed qty adjusts stock. Mistyped after confirm? Correct while this checkpoint
                    is open. Close asks you to review a summary first.
                  </p>
                ) : null}

                <div ref={linesTopRef} />
                <DataTable>
                  <DataTableHeader>
                    <DataTableHead>Product</DataTableHead>
                    <DataTableHead align="right">Was</DataTableHead>
                    <DataTableHead align="right">Stock at hand</DataTableHead>
                    <DataTableHead align="right">Action</DataTableHead>
                  </DataTableHeader>
                  <DataTableBody>
                    {sortedLines.map((line) => (
                      <DataTableRow key={line.id}>
                        <DataTableCell>
                          <div className="font-medium">{line.product_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {[line.product_sku, line.variant_label].filter(Boolean).join(' · ')}
                          </div>
                        </DataTableCell>
                        <DataTableCell align="right">{line.system_qty_at_open}</DataTableCell>
                        <DataTableCell align="right">
                          {detail.status === 'open' ? (
                            <Input
                              type="number"
                              min={0}
                              className="ml-auto h-9 w-24 text-right"
                              value={countDrafts[line.id] ?? ''}
                              disabled={busy}
                              onChange={(e) =>
                                setCountDrafts((prev) => ({
                                  ...prev,
                                  [line.id]: e.target.value,
                                }))
                              }
                            />
                          ) : (
                            line.counted_qty ?? line.system_qty_at_open
                          )}
                        </DataTableCell>
                        <DataTableCell align="right">
                          {detail.status === 'open' ? (
                            <div className="flex flex-col items-end gap-1">
                              {line.status === 'counted' ? (
                                <Badge variant="success">Counted</Badge>
                              ) : null}
                              <Button
                                type="button"
                                size="sm"
                                variant={line.status === 'counted' ? 'outline' : 'default'}
                                disabled={
                                  busy || !isCountDraftSavable(line, countDrafts[line.id])
                                }
                                title={
                                  line.status === 'counted'
                                    ? isCountDraftChanged(line, countDrafts[line.id])
                                      ? 'Correct this count'
                                      : 'Change the quantity to correct'
                                    : isCountDraftChanged(line, countDrafts[line.id])
                                      ? 'Save counted qty (adjusts stock)'
                                      : 'Confirm same as system (no stock change)'
                                }
                                onClick={() => handleCount(line)}
                              >
                                {line.status === 'counted'
                                  ? 'Correct'
                                  : isCountDraftChanged(line, countDrafts[line.id])
                                    ? 'Save count'
                                    : 'Confirm'}
                              </Button>
                            </div>
                          ) : line.status === 'counted' ? (
                            <Badge variant="success">Counted</Badge>
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

      <ConfirmDialog
        isOpen={showCloseConfirm}
        type="warning"
        title="Close this checkpoint?"
        message="Closing locks counts and sets the reporting baseline. Review the summary below."
        confirmText="Close checkpoint"
        cancelText="Keep open"
        busy={busy}
        onCancel={() => {
          if (busy) return;
          setShowCloseConfirm(false);
          setCloseSummary(null);
        }}
        onConfirm={handleCloseConfirm}
      >
        {closeSummary ? (
          <div className="space-y-3 rounded-md border bg-muted/30 px-3 py-3 text-sm">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">Lines</p>
                <p className="font-semibold tabular-nums">{closeSummary.counted}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                  Unchanged
                </p>
                <p className="font-semibold tabular-nums">{closeSummary.unchanged}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                  Adjusted up
                </p>
                <p className="font-semibold tabular-nums text-emerald-700">
                  {closeSummary.adjustedUp}
                  {closeSummary.unitsUp > 0 ? ` (+${closeSummary.unitsUp})` : ''}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                  Adjusted down
                </p>
                <p className="font-semibold tabular-nums text-rose-700">
                  {closeSummary.adjustedDown}
                  {closeSummary.unitsDown > 0 ? ` (−${closeSummary.unitsDown})` : ''}
                </p>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                  Net units
                </p>
                <p className="font-semibold tabular-nums">
                  {closeSummary.netUnits > 0 ? '+' : ''}
                  {closeSummary.netUnits}
                </p>
              </div>
            </div>
            {closeSummary.adjustments.length > 0 ? (
              <div>
                <p className="mb-1 text-xs font-semibold text-muted-foreground">
                  Largest adjustments
                </p>
                <ul className="max-h-36 space-y-1 overflow-y-auto text-xs">
                  {closeSummary.adjustments.slice(0, 8).map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span className="min-w-0 truncate">
                        {row.name}
                        {row.variant ? ` · ${row.variant}` : ''}
                      </span>
                      <span className="shrink-0 tabular-nums">
                        {row.was} → {row.now}{' '}
                        <span
                          className={
                            row.delta > 0 ? 'text-emerald-700' : 'text-rose-700'
                          }
                        >
                          ({row.delta > 0 ? '+' : ''}
                          {row.delta})
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Every line matches system stock — closing will not change inventory quantities.
              </p>
            )}
          </div>
        ) : null}
      </ConfirmDialog>

      <Dialog
        open={showOpen}
        onOpenChange={(open) => {
          setShowOpen(open);
          if (!open) clearFormBanner(setOpenFormBanner);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Open stock checkpoint</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <FormBanner
              message={openFormBanner?.message}
              type={openFormBanner?.type || 'error'}
              onDismiss={() => clearFormBanner(setOpenFormBanner)}
            />
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
