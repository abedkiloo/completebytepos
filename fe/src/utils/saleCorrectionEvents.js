/** Fired after a returned sale is sent back for approval from Terminal. */
export const SALE_CORRECTION_SUBMITTED_EVENT = 'sale-correction-submitted';

export function dispatchSaleCorrectionSubmitted(detail = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(SALE_CORRECTION_SUBMITTED_EVENT, { detail }),
  );
}
