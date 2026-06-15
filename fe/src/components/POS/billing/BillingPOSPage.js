import React, { useRef } from 'react';
import {
  Search,
  ScanBarcode,
  ShoppingCart,
  Trash2,
  UserPlus,
  User,
  Check,
  Loader2,
} from 'lucide-react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Badge } from '../../ui/badge';
import { cn } from '../../../lib/cn';
import { formatCurrency } from '../../../utils/formatters';
import { useBillingPOSState } from './useBillingPOSState';
import VariantSelector from '../VariantSelector';
import { CartQtyInput } from '../CartQtyInput';
import { getLineStockCap } from '../v2/usePOSState';
import PosCartRecoveryDialog from '../PosCartRecoveryDialog';
import PartialPaymentCustomerDialog from './PartialPaymentCustomerDialog';
import CustomerFormModal from '../../Customers/CustomerFormModal';
import ReceiptDialog from '../v2/ReceiptDialog';
import { toast } from '../../../utils/toast';
import { getSellableStock, isProductOutOfStock } from '../../../utils/productStock';
import { useStoreSettings } from '../../../hooks/useStoreSettings';
import {
  filterEnabledPaymentMethods,
  paymentReferenceLabel,
  paymentReferencePlaceholder,
  paymentReferenceRequired,
} from '../../../utils/paymentMethods';
import { isManagerOrAdminFromStorage } from '../../../utils/roleAccess';
import { useModuleSettings } from '../../../hooks/useModuleSettings';
import { canQuickAddCustomerAtPos } from '../../../utils/customerDisplay';
import {
  BILLING_AMOUNT_RECEIVED_CLASS,
  BILLING_INVOICE_CARD_CLASS,
  BILLING_PARTIAL_PAYMENT_BLOCK_CLASS,
  BILLING_PAYMENT_METHODS_GRID_CLASS,
  BILLING_PAYMENT_SECTION_CLASS,
  BILLING_RIGHT_COLUMN_CLASS,
  BILLING_TOTALS_SECTION_CLASS,
} from './billingInvoiceLayout';

export default function BillingPOSPage() {
  const state = useBillingPOSState();
  const { settings } = useStoreSettings();
  const paymentModes = filterEnabledPaymentMethods(settings.enabled_payment_methods).map((m) => ({
    id: m.id,
    label: m.id === 'mpesa' ? 'UPI / M-PESA' : m.label,
  }));
  const searchRef = useRef(null);
  const customerSearchRef = useRef(null);
  const [showNewCustomer, setShowNewCustomer] = React.useState(false);
  const { settings: customerModuleSettings } = useModuleSettings('customers');
  const canAddCustomer = canQuickAddCustomerAtPos(
    isManagerOrAdminFromStorage(),
    customerModuleSettings
  );

  if (state.loadingHolding) {
    return (
      <div className="flex h-[70vh] items-center justify-center text-muted-foreground">
          <Loader2 className="mr-2 h-6 w-6 animate-spin text-primary" />
          Loading register…
        </div>
    );
  }

  return (
    <>
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col bg-slate-50">
        {/* Top bar */}
        <div className="flex items-center justify-between border-b bg-white px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Terminal POS</h1>
            <p className="text-xs text-muted-foreground">
              Draft invoice saved automatically
              {state.holdingNumber && (
                <span className="ml-2 font-mono text-primary">{state.holdingNumber}</span>
              )}
              {state.syncingHolding && (
                <span className="ml-2 text-amber-600">· saving…</span>
              )}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={state.clearCart}>
            New sale
          </Button>
        </div>

        <div className="grid flex-1 gap-4 p-4 lg:grid-cols-[1fr_minmax(300px,380px)]">
          {/* Left: search + cart */}
          <div className="flex flex-col gap-4">
            {/* Scan / search */}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
                <ScanBarcode className="h-4 w-4 text-primary" />
                Scan / Search Product
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  ref={searchRef}
                  autoFocus
                  placeholder="Scan barcode or type product name…"
                  value={state.searchQuery}
                  onChange={(e) => state.setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && state.searchResults[0]) {
                      const first = state.searchResults[0];
                      if (state.validateStock && isProductOutOfStock(first)) {
                        toast.warning(`${first.name} is out of stock`);
                        return;
                      }
                      state.addToCart(first);
                    }
                  }}
                  className="h-11 pl-10"
                />
              </div>
              {state.searchQuery && (
                <ul className="mt-2 max-h-48 overflow-y-auto rounded-lg border">
                  {state.searching && (
                    <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>
                  )}
                  {!state.searching && state.searchResults.length === 0 && (
                    <li className="px-3 py-2 text-sm text-muted-foreground">No products found</li>
                  )}
                  {state.searchResults.map((p) => {
                    const outOfStock = state.validateStock && isProductOutOfStock(p);
                    const stock = getSellableStock(p);
                    return (
                      <li key={p.id}>
                        <button
                          type="button"
                          disabled={outOfStock}
                          aria-disabled={outOfStock}
                          className={cn(
                            'flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm',
                            outOfStock
                              ? 'cursor-not-allowed bg-red-50 text-red-700'
                              : 'hover:bg-primary/5'
                          )}
                          onClick={() => !outOfStock && state.addToCart(p)}
                        >
                          <span className="min-w-0 flex-1">
                            <span className="block font-medium">{p.name}</span>
                          </span>
                          <span className="flex shrink-0 flex-col items-end gap-0.5">
                            <span
                              className={cn(
                                'tabular-nums',
                                outOfStock ? 'text-red-600' : 'text-primary'
                              )}
                            >
                              {formatCurrency(p.price)}
                            </span>
                            {stock !== null && (
                              <span
                                className={cn(
                                  'text-[11px] tabular-nums',
                                  outOfStock ? 'font-medium text-red-600' : 'text-muted-foreground'
                                )}
                              >
                                {outOfStock ? 'Out of stock' : `Stock: ${stock}`}
                              </span>
                            )}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Cart table */}
            <div className="flex flex-1 flex-col rounded-xl border bg-white shadow-sm">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-2 font-medium">
                  <ShoppingCart className="h-4 w-4 text-primary" />
                  Cart
                  <Badge variant="secondary">{state.itemCount} items</Badge>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={state.clearCart}
                  disabled={state.cart.length === 0}
                  aria-label="Clear cart"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-2 font-medium">Item</th>
                      <th className="px-2 py-2 font-medium text-right">MRP</th>
                      <th className="px-2 py-2 font-medium text-right">Selling</th>
                      <th className="px-2 py-2 font-medium text-center">Qty</th>
                      <th className="px-2 py-2 font-medium text-right">Total</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {state.cart.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                          Search and add products to start a holding invoice
                        </td>
                      </tr>
                    )}
                    {state.cart.map((item) => {
                      const key = item.variant_id
                        ? `${item.id}-${item.variant_id}`
                        : `${item.id}`;
                      const lineTotal = item.price * item.quantity;
                      const stockCap = state.validateStock ? getLineStockCap(item) : null;
                      return (
                        <tr key={key} className="border-b last:border-0">
                          <td className="px-4 py-3">
                            <div className="font-medium">{item.name}</div>
                          </td>
                          <td className="px-2 py-3 text-right tabular-nums text-muted-foreground">
                            {formatCurrency(item.mrp ?? item.price)}
                          </td>
                          <td className="px-2 py-3 text-right tabular-nums font-medium">
                            {formatCurrency(item.selling_price ?? item.price)}
                          </td>
                          <td className="px-2 py-3">
                            <CartQtyInput
                              quantity={item.quantity}
                              stockCap={stockCap}
                              onDelta={(delta) => state.updateQty(key, delta)}
                              onSetQuantity={(qty) => state.setQty(key, qty)}
                              disablePlus={
                                stockCap !== null && item.quantity >= stockCap
                              }
                            />
                          </td>
                          <td className="px-2 py-3 text-right font-medium tabular-nums">
                            {formatCurrency(lineTotal)}
                          </td>
                          <td className="px-2 py-3">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => state.removeLine(key)}
                            >
                              <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {state.cart.length > 0 && (
                    <tfoot>
                      <tr className="bg-slate-50 font-medium">
                        <td className="px-4 py-2" colSpan={4}>
                          {state.itemCount} items
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums" colSpan={2}>
                          {formatCurrency(state.subtotal)}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          </div>

          {/* Right: customer + invoice */}
          <div className={BILLING_RIGHT_COLUMN_CLASS}>
            {/* Customer */}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <User className="h-4 w-4 text-primary" />
                  Customer
                </div>
                {canAddCustomer && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1"
                    onClick={() => setShowNewCustomer(true)}
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    New Customer
                  </Button>
                )}
              </div>
              <div className="mb-2 flex items-center justify-between rounded-lg bg-primary/5 px-3 py-2">
                <div>
                  <div className="font-medium">{state.selectedCustomer?.name}</div>
                  {state.selectedCustomer?.phone && (
                    <div className="text-xs text-muted-foreground">
                      {state.selectedCustomer.phone}
                    </div>
                  )}
                  {state.isWalkInCustomer(state.selectedCustomer) && (
                    <div className="text-xs text-muted-foreground">Default for cash sales</div>
                  )}
                </div>
                {!state.requireCustomer &&
                  !state.isWalkInCustomer(state.selectedCustomer) && (
                  <Button variant="ghost" size="sm" onClick={state.selectWalkInCustomer}>
                    Walk-in
                  </Button>
                )}
              </div>
              <Input
                ref={customerSearchRef}
                placeholder="Search by name or phone…"
                value={state.customerQuery}
                onChange={(e) => state.setCustomerQuery(e.target.value)}
                className="h-10"
                aria-label="Search customer by name or phone"
              />
              {state.customerQuery && (
                <ul className="mt-2 max-h-32 overflow-y-auto rounded-lg border">
                  {state.filteredCustomers.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                        onClick={() => {
                          state.setSelectedCustomer(c);
                          state.setCustomerQuery('');
                        }}
                      >
                        {c.name}
                        {c.phone && (
                          <span className="ml-2 text-muted-foreground">{c.phone}</span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Invoice details */}
            <div
              className={BILLING_INVOICE_CARD_CLASS}
              data-testid="billing-invoice-details"
            >
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Invoice Details</h2>

              {state.showDiscount && (
              <div className="mb-4">
                <Label className="mb-1.5 text-xs text-muted-foreground">Discount</Label>
                <div className="flex gap-2">
                  <div className="flex rounded-md border">
                    <button
                      type="button"
                      className={cn(
                        'px-3 py-2 text-sm',
                        state.discountType === 'flat' && 'bg-primary text-primary-foreground'
                      )}
                      onClick={() => state.setDiscountType('flat')}
                    >
                      KES
                    </button>
                    <button
                      type="button"
                      className={cn(
                        'px-3 py-2 text-sm',
                        state.discountType === 'percentage' && 'bg-primary text-primary-foreground'
                      )}
                      onClick={() => state.setDiscountType('percentage')}
                    >
                      %
                    </button>
                  </div>
                  <Input
                    type="number"
                    min="0"
                    value={state.discount}
                    onChange={(e) => state.setDiscount(e.target.value)}
                    className="h-10 flex-1"
                  />
                </div>
              </div>
              )}

              {state.showTax && (
              <div className="mb-4">
                <Label className="mb-1.5 text-xs text-muted-foreground">Tax % (GST)</Label>
                <Input
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={state.taxPct}
                  onChange={(e) => state.setTaxPct(e.target.value)}
                  className="h-10"
                />
              </div>
              )}

              <section
                className={BILLING_PAYMENT_SECTION_CLASS}
                data-testid="billing-payment-section"
              >
                <Label className="block text-xs font-medium text-muted-foreground">
                  Payment Mode
                </Label>

                {state.allowPartialPayment && (
                  <div className={BILLING_PARTIAL_PAYMENT_BLOCK_CLASS}>
                    <label className="flex cursor-pointer items-start gap-2.5 text-sm leading-snug">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 shrink-0"
                        checked={state.partialPayment}
                        onChange={(e) => state.attemptSetPartialPayment(e.target.checked)}
                        aria-describedby="partial-payment-hint"
                      />
                      <span>Partial payment (balance on customer account)</span>
                    </label>
                    {state.isWalkInCustomer(state.selectedCustomer) && (
                      <p
                        id="partial-payment-hint"
                        className="text-xs leading-relaxed text-muted-foreground"
                      >
                        Select or add a customer to charge the balance to their account.
                      </p>
                    )}
                  </div>
                )}

                <div
                  className={cn(
                    BILLING_PAYMENT_METHODS_GRID_CLASS,
                    paymentModes.length <= 2 ? 'grid-cols-2' : 'grid-cols-3'
                  )}
                >
                  {paymentModes.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => state.setPaymentMethod(m.id)}
                      className={cn(
                        'min-h-[2.75rem] rounded-lg border-2 px-2 py-3 text-center text-sm font-medium transition-colors',
                        state.paymentMethod === m.id
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-slate-200 hover:border-slate-300'
                      )}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>

                {paymentReferenceRequired(state.paymentMethod) ? (
                  <div className="mt-3 space-y-1">
                    <Label
                      htmlFor="billing-payment-reference"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      {paymentReferenceLabel(state.paymentMethod)} *
                    </Label>
                    <Input
                      id="billing-payment-reference"
                      type="text"
                      value={state.paymentReference}
                      onChange={(e) => state.setPaymentReference(e.target.value)}
                      placeholder={paymentReferencePlaceholder(state.paymentMethod)}
                      className="h-10 font-mono text-sm"
                      autoComplete="off"
                    />
                  </div>
                ) : null}

                {state.paymentMethod !== 'other' && (
                  <div
                    className={BILLING_AMOUNT_RECEIVED_CLASS}
                    data-testid="billing-amount-received"
                  >
                    <Label
                      htmlFor="billing-amount-received"
                      className="block text-xs font-medium text-muted-foreground"
                    >
                      Amount received
                    </Label>
                    <Input
                      id="billing-amount-received"
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="0.01"
                      value={state.amountPaid}
                      onChange={(e) => state.setAmountPaid(e.target.value)}
                      placeholder="0.00"
                      className="h-11 text-right text-lg font-semibold tabular-nums"
                    />
                  </div>
                )}
              </section>

              <dl className={BILLING_TOTALS_SECTION_CLASS}>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Subtotal</dt>
                  <dd className="tabular-nums">{formatCurrency(state.subtotal)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Discount</dt>
                  <dd className="tabular-nums text-destructive">
                    −{formatCurrency(state.discountAmount)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Taxable value</dt>
                  <dd className="tabular-nums">{formatCurrency(state.taxableValue)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">GST</dt>
                  <dd className="tabular-nums">{formatCurrency(state.taxAmount)}</dd>
                </div>
                <div className="flex justify-between border-t pt-2 text-base font-bold">
                  <dt>Grand Total</dt>
                  <dd className="tabular-nums text-primary">{formatCurrency(state.total)}</dd>
                </div>
              </dl>

              <Button
                className="mt-4 h-12 w-full gap-2 text-base font-semibold"
                disabled={state.submitting || state.cart.length === 0}
                onClick={state.checkout}
              >
                {state.submitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Check className="h-5 w-5" />
                )}
                Checkout · view receipt
              </Button>
            </div>
          </div>
        </div>
      </div>

      <PartialPaymentCustomerDialog
        open={state.partialPaymentCustomerPrompt}
        canAddCustomer={canAddCustomer}
        onClose={state.closePartialPaymentCustomerPrompt}
        onSelectCustomer={() => {
          state.closePartialPaymentCustomerPrompt();
          customerSearchRef.current?.focus();
          customerSearchRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
        }}
        onAddCustomer={() => {
          state.closePartialPaymentCustomerPrompt();
          if (canAddCustomer) setShowNewCustomer(true);
        }}
      />

      <PosCartRecoveryDialog
        open={Boolean(state.cartRecovery)}
        source={state.cartRecovery?.source || 'holding'}
        itemCount={state.cartRecovery?.itemCount || 0}
        label={state.cartRecovery?.label}
        onContinue={state.continueCartRecovery}
        onStartNew={state.startNewSaleFromRecovery}
        busy={state.recoveryBusy}
      />

      {state.variantPickerProduct && (
        <VariantSelector
          product={state.variantPickerProduct}
          validateStock={state.validateStock}
          onSelect={(line) => {
            state.addToCart(state.variantPickerProduct, line);
            state.setVariantPickerProduct(null);
          }}
          onClose={() => state.setVariantPickerProduct(null)}
        />
      )}

      {canAddCustomer && (
        <CustomerFormModal
          isOpen={showNewCustomer}
          onClose={() => setShowNewCustomer(false)}
          onCustomerCreated={async (customer) => {
            await state.loadCustomers();
            state.setSelectedCustomer(customer);
            state.setCustomerQuery('');
            setShowNewCustomer(false);
            toast.success('Customer added and selected for this sale');
          }}
        />
      )}

      <ReceiptDialog
        sale={state.lastSale}
        open={state.showReceipt}
        onOpenChange={state.setShowReceipt}
        autoPrint={settings.receipt_auto_print}
      />
    </>
  );
}
