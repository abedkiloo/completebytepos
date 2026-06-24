/**
 * Layout classes for Terminal POS invoice column (single source for UI + tests).
 */

/** Scrollable left column (search + cart table) inside the fixed viewport. */
export const BILLING_LEFT_COLUMN_CLASS =
  'app-scroll-region flex min-h-0 flex-col gap-4 pr-1';

export const BILLING_RIGHT_COLUMN_CLASS =
  'app-scroll-region flex min-h-0 flex-col gap-4 pr-1 lg:sticky lg:top-4 lg:max-h-[calc(100dvh-7rem)]';

export const BILLING_INVOICE_CARD_CLASS =
  'flex flex-col rounded-xl border bg-white p-4 shadow-sm';

export const BILLING_PAYMENT_SECTION_CLASS =
  'space-y-4 border-b border-slate-100 pb-4';

export const BILLING_PARTIAL_PAYMENT_BLOCK_CLASS =
  'space-y-2 rounded-lg border border-slate-100 bg-slate-50/90 px-3 py-3';

export const BILLING_PAYMENT_METHODS_GRID_CLASS = 'grid gap-2.5';

export const BILLING_AMOUNT_RECEIVED_CLASS = 'space-y-2';

export const BILLING_TOTALS_SECTION_CLASS =
  'mt-4 space-y-2 border-t border-slate-100 pt-4 text-sm';
