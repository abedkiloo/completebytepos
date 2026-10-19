/**
 * Stock checkpoint count drafts.
 *
 * TODO(checkpoint-confirm-unchanged): Allow saving a line when stock at hand
 * matches system qty (confirm "no change") so counts can close without forcing
 * a fake delta. Until then, Save stays disabled unless the draft differs.
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
 * True when draft is a valid qty and differs from the snapshot at open.
 * Unchanged drafts cannot be saved yet (see TODO above).
 */
export function isCountDraftChanged(line, draftRaw) {
  const qty = parseCountDraft(draftRaw);
  if (qty === null) return false;
  return qty !== systemQtyAtOpen(line);
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
 * Build bulk-count payload from pending lines that have a changed draft.
 * @returns {{ payload: Array<{line_id:number, counted_qty:number}> }}
 */
export function buildChangedCountPayload(pendingLines, countDrafts) {
  const payload = [];
  for (const line of pendingLines || []) {
    const raw = countDrafts?.[line.id];
    if (!isCountDraftChanged(line, raw)) continue;
    // isCountDraftChanged already validated parseCountDraft(raw).
    payload.push({ line_id: line.id, counted_qty: parseCountDraft(raw) });
  }
  return { payload };
}

export function hasAnyChangedPendingDraft(pendingLines, countDrafts) {
  return (pendingLines || []).some((line) =>
    isCountDraftChanged(line, countDrafts?.[line.id])
  );
}
