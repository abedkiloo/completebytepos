/**
 * Detect whether a returned sale still matches the snapshot taken when it
 * was sent back for correction (Was → Now).
 */
export function correctionLooksUnchanged(snapshot, {
  total = 0,
  paid = 0,
  itemCount = 0,
  paymentMethod = '',
} = {}) {
  if (!snapshot) return false;
  const moneyClose = (a, b) => Math.abs((Number(a) || 0) - (Number(b) || 0)) < 0.009;
  if (!moneyClose(snapshot.total, total)) return false;
  if (!moneyClose(snapshot.paid, paid)) return false;
  if (
    snapshot.itemCount != null
    && Number(snapshot.itemCount) !== Number(itemCount)
  ) {
    return false;
  }
  if (
    snapshot.paymentMethod
    && String(snapshot.paymentMethod).toLowerCase()
      !== String(paymentMethod || '').toLowerCase()
  ) {
    return false;
  }
  return true;
}
