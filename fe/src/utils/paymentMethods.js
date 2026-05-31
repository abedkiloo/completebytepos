import {
  Banknote,
  Smartphone,
  Wallet,
  CreditCard,
} from 'lucide-react';

/** All supported checkout payment methods. */
export const PAYMENT_METHODS = [
  { id: 'cash', label: 'Cash', icon: Banknote, requiresAmount: true },
  { id: 'mpesa', label: 'M-Pesa', icon: Smartphone, requiresAmount: true },
  { id: 'wallet', label: 'Wallet', icon: Wallet, requiresAmount: false },
  { id: 'card', label: 'Card', icon: CreditCard, requiresAmount: false },
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
