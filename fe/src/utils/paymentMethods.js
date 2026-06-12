import {
  Banknote,
  Smartphone,
  Wallet,
  CreditCard,
} from 'lucide-react';

/** All supported checkout payment methods. */
export const PAYMENT_METHODS = [
  { id: 'cash', label: 'Cash', icon: Banknote, requiresAmount: true, requiresReference: false },
  {
    id: 'mpesa',
    label: 'M-Pesa',
    icon: Smartphone,
    requiresAmount: true,
    requiresReference: true,
    referenceLabel: 'M-Pesa code',
    referencePlaceholder: 'e.g. QHX1ABC2DE',
  },
  {
    id: 'wallet',
    label: 'Wallet',
    icon: Wallet,
    requiresAmount: false,
    requiresReference: false,
  },
  {
    id: 'card',
    label: 'Card',
    icon: CreditCard,
    requiresAmount: false,
    requiresReference: true,
    referenceLabel: 'Card reference',
    referencePlaceholder: 'Last 4 digits or approval code',
  },
];

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
