/**
 * Stock checkpoint count drafts.
 *
 * Pending lines can be confirmed at system qty (no stock change) so checkpoints
 * can close without forcing a fake delta. Counted lines still require a real
 * qty change before "Correct" is enabled.
 */

/** @returns {number|null} */
export function parseCountDraft(raw) {
  if (raw === null || raw === undefined) return null;
  const trimmed = String(raw).trim();
  if (trimmed === '') return null;
  const qty = parseInt(trimmed, 10);
  if (Number.isNaN(qty) || qty < 0) return null;
  return qty;
}

export function systemQtyAtOpen(line) {
  return Number(line?.system_qty_at_open ?? 0);
}

/**
 * True when draft is a valid qty and differs from the baseline for this line.
 * Pending: baseline is system qty at open.
 * Counted (correction): baseline is the saved counted qty.
 */
export function isCountDraftChanged(line, draftRaw) {
  const qty = parseCountDraft(draftRaw);
  if (qty === null) return false;
  if (line?.status === 'counted') {
    return qty !== Number(line.counted_qty ?? 0);
  }
  return qty !== systemQtyAtOpen(line);
}

/**
 * Pending lines: any valid qty is savable (including unchanged = confirm).
 * Counted lines: only a changed qty can be corrected.
 */
export function isCountDraftSavable(line, draftRaw) {
  const qty = parseCountDraft(draftRaw);
  if (qty === null) return false;
  if (line?.status === 'counted') {
    return isCountDraftChanged(line, draftRaw);
  }
  return true;
}

function countedAtMs(line) {
  if (!line || !line.counted_at) return 0;
  const ms = Date.parse(line.counted_at);
  return Number.isFinite(ms) ? ms : 0;
}

function lineId(line) {
  return line && line.id != null ? Number(line.id) : 0;
}

/** Pending lines first; among counted, oldest count first. */
export function sortCheckpointLines(lines) {
  return [...(lines || [])].sort((a, b) => {
    const aDone = a.status === 'counted' ? 1 : 0;
    const bDone = b.status === 'counted' ? 1 : 0;
    if (aDone !== bDone) return aDone - bDone;
    if (aDone && bDone) {
      const delta = countedAtMs(a) - countedAtMs(b);
      if (delta !== 0) return delta;
    }
    return lineId(a) - lineId(b);
  });
}

/**
 * Build bulk-count payload from pending lines with a valid draft
 * (changed or confirmed unchanged).
 * @returns {{ payload: Array<{line_id:number, counted_qty:number}> }}
 */
export function buildPendingCountPayload(pendingLines, countDrafts) {
  const payload = [];
  for (const line of pendingLines || []) {
    const raw = countDrafts?.[line.id];
    if (!isCountDraftSavable(line, raw)) continue;
    payload.push({ line_id: line.id, counted_qty: parseCountDraft(raw) });
  }
  return { payload };
}

/** @deprecated Prefer buildPendingCountPayload — kept for callers that want deltas only. */
export function buildChangedCountPayload(pendingLines, countDrafts) {
  const payload = [];
  for (const line of pendingLines || []) {
    const raw = countDrafts?.[line.id];
    if (!isCountDraftChanged(line, raw)) continue;
    payload.push({ line_id: line.id, counted_qty: parseCountDraft(raw) });
  }
  return { payload };
}

export function hasAnySavablePendingDraft(pendingLines, countDrafts) {
  return (pendingLines || []).some((line) =>
    isCountDraftSavable(line, countDrafts?.[line.id])
  );
}

export function hasAnyChangedPendingDraft(pendingLines, countDrafts) {
  return (pendingLines || []).some((line) =>
    isCountDraftChanged(line, countDrafts?.[line.id])
  );
}

/**
 * Summary of counted lines for the close-checkpoint confirmation.
 */
export function buildCloseCheckpointSummary(lines) {
  const counted = (lines || []).filter((line) => line?.status === 'counted');
  const pending = (lines || []).filter((line) => line?.status !== 'counted');
  let unchanged = 0;
  let adjustedUp = 0;
  let adjustedDown = 0;
  let unitsUp = 0;
  let unitsDown = 0;
  const adjustments = [];

  for (const line of counted) {
    const was = systemQtyAtOpen(line);
    const now = Number(line.counted_qty ?? was);
    const delta = now - was;
    if (delta === 0) {
      unchanged += 1;
      continue;
    }
    if (delta > 0) {
      adjustedUp += 1;
      unitsUp += delta;
    } else {
      adjustedDown += 1;
      unitsDown += Math.abs(delta);
    }
    adjustments.push({
      id: line.id,
      name: line.product_name || 'Product',
      sku: line.product_sku || '',
      variant: line.variant_label || '',
      was,
      now,
      delta,
    });
  }

  adjustments.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  return {
    totalLines: (lines || []).length,
    counted: counted.length,
    pending: pending.length,
    unchanged,
    adjustedUp,
    adjustedDown,
    unitsUp,
    unitsDown,
    netUnits: unitsUp - unitsDown,
    adjustments,
  };
}
