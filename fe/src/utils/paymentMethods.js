import {
  Banknote,
  Smartphone,
  Wallet,
} from 'lucide-react';

/** Checkout + collection methods. Card / other / bank are no longer offered. */
export const PAYMENT_METHODS = [
  { id: 'cash', label: 'Cash', icon: Banknote, requiresAmount: true, requiresReference: false },
  {
    id: 'mpesa',
    label: 'M-Pesa',
    icon: Smartphone,
    requiresAmount: true,
    requiresReference: true,
    referenceLabel: 'M-Pesa code',
    referencePlaceholder: 'e.g. QHX7K2L9M1',
  },
  {
    id: 'wallet',
    label: 'Wallet',
    icon: Wallet,
    requiresAmount: false,
    requiresReference: false,
  },
];

/** Cash and M-Pesa only — debt collection, invoice payments, sales. */
export const COLLECTION_PAYMENT_METHODS = PAYMENT_METHODS.filter(
  (m) => m.id === 'cash' || m.id === 'mpesa'
);

export function filterEnabledPaymentMethods(enabledIds) {
  const set = new Set(
    (enabledIds?.length ? enabledIds : PAYMENT_METHODS.map((m) => m.id)).map((id) =>
      String(id).toLowerCase()
    )
  );
  const filtered = PAYMENT_METHODS.filter((m) => set.has(m.id));
  return filtered.length ? filtered : [PAYMENT_METHODS[0]];
}

export function getPaymentMethodMeta(methodId) {
  return PAYMENT_METHODS.find((m) => m.id === methodId) || PAYMENT_METHODS[0];
}

export function paymentReferenceRequired(methodId) {
  return Boolean(getPaymentMethodMeta(methodId).requiresReference);
}

export function paymentReferenceLabel(methodId) {
  const meta = getPaymentMethodMeta(methodId);
  return meta.referenceLabel || 'Payment reference';
}

export function paymentReferencePlaceholder(methodId) {
  const meta = getPaymentMethodMeta(methodId);
  return meta.referencePlaceholder || 'Enter reference';
}

export function paymentMethodLabel(methodId) {
  if (methodId === 'installments') return 'Installments';
  if (methodId === 'other') return 'Other';
  if (methodId === 'card') return 'Card';
  if (methodId === 'bank_transfer') return 'Bank Transfer';
  if (methodId === 'cheque') return 'Cheque';
  return getPaymentMethodMeta(methodId).label;
}
