import React, { useRef } from 'react';
import {
  Search,
  ScanBarcode,
  ShoppingCart,
  Trash2,
  UserPlus,
  User,
  Check,
  Minus,
  Plus,
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
import CustomerFormModal from '../../Customers/CustomerFormModal';
import ReceiptDialog from '../v2/ReceiptDialog';
import { toast } from '../../../utils/toast';
import { getSellableStock, isProductOutOfStock } from '../../../utils/productStock';

const PAYMENT_MODES = [
  { id: 'cash', label: 'Cash' },
  { id: 'mpesa', label: 'UPI / M-PESA' },
  { id: 'card', label: 'Card' },
];

export default function BillingPOSPage() {
  const state = useBillingPOSState();
  const searchRef = useRef(null);
  const [showNewCustomer, setShowNewCustomer] = React.useState(false);

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

        <div className="grid flex-1 gap-4 p-4 lg:grid-cols-[1fr_340px]">
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
                      if (isProductOutOfStock(first)) {
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
                    const outOfStock = isProductOutOfStock(p);
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
                            {p.sku && (
                              <span className="block text-xs opacity-80">{p.sku}</span>
                            )}
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
                      return (
                        <tr key={key} className="border-b last:border-0">
                          <td className="px-4 py-3">
                            <div className="font-medium">{item.name}</div>
                            {item.sku && (
                              <div className="text-xs text-muted-foreground">{item.sku}</div>
                            )}
                          </td>
                          <td className="px-2 py-3 text-right tabular-nums text-muted-foreground">
                            {formatCurrency(item.mrp ?? item.price)}
                          </td>
                          <td className="px-2 py-3 text-right tabular-nums font-medium">
                            {formatCurrency(item.selling_price ?? item.price)}
                          </td>
                          <td className="px-2 py-3">
                            <div className="flex items-center justify-center gap-1">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => state.updateQty(key, -1)}
                              >
                                <Minus className="h-3 w-3" />
                              </Button>
                              <span className="w-8 text-center tabular-nums font-medium">
                                {item.quantity}
                              </span>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => state.updateQty(key, 1)}
                              >
                                <Plus className="h-3 w-3" />
                              </Button>
                            </div>
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
          <div className="flex flex-col gap-4">
            {/* Customer */}
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <User className="h-4 w-4 text-primary" />
                  Customer
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-1"
                  onClick={() => setShowNewCustomer(true)}
                >
                  <UserPlus className="h-3.5 w-3.5" />
                  New Customer
                </Button>
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
                {!state.isWalkInCustomer(state.selectedCustomer) && (
                  <Button variant="ghost" size="sm" onClick={state.selectWalkInCustomer}>
                    Walk-in
                  </Button>
                )}
              </div>
              <Input
                placeholder="Search by name or phone…"
                value={state.customerQuery}
                onChange={(e) => state.setCustomerQuery(e.target.value)}
                className="h-10"
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
            <div className="flex flex-1 flex-col rounded-xl border bg-white p-4 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-slate-800">Invoice Details</h2>

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

              <div className="mb-3">
                <Label className="mb-2 text-xs text-muted-foreground">Payment Mode</Label>
                <label className="mb-2 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={state.partialPayment}
                    onChange={(e) => state.setPartialPayment(e.target.checked)}
                  />
                  Partial payment (balance on customer account)
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {PAYMENT_MODES.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => state.setPaymentMethod(m.id)}
                      className={cn(
                        'rounded-lg border-2 py-3 text-center text-sm font-medium transition-colors',
                        state.paymentMethod === m.id
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-slate-200 hover:border-slate-300'
                      )}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              {state.paymentMethod !== 'other' && (
                <div className="mb-4">
                  <Label className="mb-1.5 text-xs text-muted-foreground">Amount received</Label>
                  <Input
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

              <dl className="space-y-2 border-t pt-3 text-sm">
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

      {state.variantPickerProduct && (
        <VariantSelector
          product={state.variantPickerProduct}
          onSelect={(variant) => {
            state.addToCart(state.variantPickerProduct, variant);
            state.setVariantPickerProduct(null);
          }}
          onClose={() => state.setVariantPickerProduct(null)}
        />
      )}

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

      <ReceiptDialog
        sale={state.lastSale}
        open={state.showReceipt}
        onOpenChange={state.setShowReceipt}
        autoPrint={false}
      />
    </>
  );
}
