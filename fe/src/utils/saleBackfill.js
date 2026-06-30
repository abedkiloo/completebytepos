/** Handle backfill API response — immediate (201) vs maker-checker queue (202). */

export function handleSaleBackfillResponse(response, { onApplied, onPending } = {}) {
  const status = response?.status;
  const data = response?.data;
  if (status === 202) {
    onPending?.(data?.pending_change, data);
    return 'pending';
  }
  onApplied?.(data);
  return 'applied';
}
