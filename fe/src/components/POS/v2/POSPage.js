import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Maximize2,
  Printer,
  BarChart3,
  RefreshCw,
  Calculator,
  ArrowLeft,
  Keyboard,
} from 'lucide-react';

import { Button } from '../../ui/button';
import { Separator } from '../../ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { toast } from '../../../utils/toast';

import { usePOSState } from './usePOSState';
import { ProductGrid } from './ProductGrid';
import { Cart } from './Cart';
import { CheckoutPanel } from './CheckoutPanel';
import { CustomerPicker } from './CustomerPicker';
import { PartialPaymentConfirm, ExcessPaymentConfirm } from './PaymentConfirmDialogs';
import ReceiptDialog from './ReceiptDialog';

import VariantSelector from '../VariantSelector';
import CustomerFormModal from '../../Customers/CustomerFormModal';
import BranchSelector from '../../BranchSelector/BranchSelector';

/**
 * Redesigned Point-of-Sale screen.
 *
 *  +-----------------------------------------------------------+
 *  | Header: back · branch · cashier · utility actions         |
 *  +-----------------------------+-----------------------------+
 *  | Products                    | Customer                    |
 *  | (search + categories +      | Cart line items             |
 *  |  grid)                      | Totals · payment · pay      |
 *  +-----------------------------+-----------------------------+
 *
 *  - No forced shipping modal. Delivery is an inline optional toggle inside
 *    CheckoutPanel.
 *  - No "Place Order" → modal → confirm dance. The big primary button is
 *    "Complete sale" and it submits directly.
 *  - Confirmation dialogs only appear for the two cases that actually need
 *    them: partial payment (debt) and excess payment (change vs wallet).
 */
export default function POSPage() {
  const navigate = useNavigate();
  const state = usePOSState();
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const searchInputRef = useRef(null);

  const handleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {
        toast.error('Fullscreen not available');
      });
    } else {
      document.exitFullscreen();
    }
  };

  const handleReprintLast = () => {
    if (state.lastSale) {
      state.setShowReceipt(true);
    } else {
      toast.info('No receipt to print yet.');
    }
  };

  const handleRefresh = () => {
    state.reloadProducts();
    toast.success('Products refreshed');
  };

  const handleCustomerCreated = (newCustomer) => {
    state.setCustomers((prev) => [newCustomer, ...prev]);
    state.setSelectedCustomer(newCustomer);
    setShowCustomerForm(false);
  };

  const requestClearCart = () => {
    if (state.cart.length === 0) return;
    setShowClearConfirm(true);
  };

  /**
   * Keyboard shortcuts. Most cashier interactions still need to be tappable
   * but a few power-user shortcuts pay back instantly:
   *
   *   F2  — focus product search
   *   F4  — focus "Amount received"
   *   F9  — submit payment
   *   ESC — close the topmost dialog (handled by Radix)
   *   ?   — show shortcuts cheat-sheet
   *
   * They're suppressed while the user is actually typing into an input or
   * textarea so we never steal a keystroke from the cart.
   */
  useEffect(() => {
    const handleKey = (e) => {
      const target = e.target;
      const isTyping =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable);

      if (e.key === 'F2') {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
        return;
      }
      if (e.key === 'F4') {
        e.preventDefault();
        document.getElementById('received')?.focus();
        return;
      }
      if (e.key === 'F9') {
        e.preventDefault();
        state.requestPayment();
        return;
      }
      if (!isTyping && (e.key === '?' || (e.shiftKey && e.key === '/'))) {
        e.preventDefault();
        setShowShortcuts(true);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [state.requestPayment]);

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/')}
          aria-label="Back to dashboard"
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>

        <div className="flex items-center gap-2">
          <img src="/logo.svg" alt="" className="h-6 w-auto" />
          <span className="hidden text-sm font-semibold sm:inline">POS</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            · {state.orderNumber}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <BranchSelector />
          <Separator orientation="vertical" className="hidden h-6 sm:block" />
          <Button variant="ghost" size="icon" onClick={handleRefresh} aria-label="Refresh products">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => navigate('/reports')} aria-label="Reports">
            <BarChart3 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={handleReprintLast} aria-label="Reprint last receipt">
            <Printer className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowShortcuts(true)}
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts"
          >
            <Keyboard className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => window.open('calculator:', '_blank')}
            aria-label="Open calculator"
          >
            <Calculator className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={handleFullscreen} aria-label="Toggle fullscreen">
            <Maximize2 className="h-4 w-4" />
          </Button>

          <Separator orientation="vertical" className="h-6" />
          <div className="flex items-center gap-2 pl-1">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
              {state.user?.username?.[0]?.toUpperCase() || 'U'}
            </span>
            <span className="hidden text-sm font-medium sm:inline">
              {state.user?.username || 'Cashier'}
            </span>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex min-h-0 flex-1">
        {/* Left: products */}
        <section className="min-h-0 min-w-0 flex-1">
          <ProductGrid
            products={state.products}
            categories={state.categories}
            loading={state.loading}
            searchQuery={state.searchQuery}
            onSearchChange={state.setSearchQuery}
            selectedCategory={state.selectedCategory}
            selectedSubcategory={state.selectedSubcategory}
            onSelectCategory={state.setSelectedCategory}
            onSelectSubcategory={state.setSelectedSubcategory}
            onAddToCart={state.tryAddToCart}
            searchInputRef={searchInputRef}
          />
        </section>

        {/* Right: cart + checkout */}
        <aside className="flex w-[24rem] shrink-0 flex-col border-l bg-background lg:w-[26rem] xl:w-[28rem]">
          <div className="border-b px-4 py-3">
            <CustomerPicker
              customers={state.customers}
              selectedCustomer={state.selectedCustomer}
              onSelect={state.setSelectedCustomer}
              onAddNew={() => setShowCustomerForm(true)}
            />
          </div>

          <div className="min-h-0 flex-1">
            <Cart
              items={state.cart}
              onAdjust={state.adjustItemQuantity}
              onRemove={state.removeFromCart}
              onClear={requestClearCart}
            />
          </div>

          <CheckoutPanel
            // totals
            subtotal={state.subtotal}
            discount={state.discount}
            discountAmount={state.discountAmount}
            setDiscount={state.setDiscount}
            discountType={state.discountType}
            setDiscountType={state.setDiscountType}
            taxPct={state.taxPct}
            setTaxPct={state.setTaxPct}
            taxAmount={state.taxAmount}
            total={state.total}
            change={state.change}
            // delivery
            deliveryEnabled={state.deliveryEnabled}
            setDeliveryEnabled={state.setDeliveryEnabled}
            deliveryCost={state.deliveryCost}
            setDeliveryCost={state.setDeliveryCost}
            // payment
            paymentMethod={state.paymentMethod}
            setPaymentMethod={state.setPaymentMethod}
            receivedAmount={state.receivedAmount}
            setReceivedAmount={state.setReceivedAmount}
            // submit
            submitting={state.submitting}
            onPay={state.requestPayment}
            itemCount={state.cartItemCount}
            hasOversell={state.hasOversell}
          />
        </aside>
      </div>

      {/* --- Dialogs --- */}

      <PartialPaymentConfirm
        open={state.showPartialPaymentConfirm}
        onOpenChange={state.setShowPartialPaymentConfirm}
        pending={state.pendingSaleData}
        customer={state.selectedCustomer}
        submitting={state.submitting}
        onConfirm={() => state.submitSale({ allowPartial: true })}
      />

      <ExcessPaymentConfirm
        open={state.showExcessPaymentConfirm}
        onOpenChange={state.setShowExcessPaymentConfirm}
        pending={state.pendingSaleData}
        customer={state.selectedCustomer}
        submitting={state.submitting}
        onConfirm={(choice) => state.submitSale({ excessChoice: choice })}
      />

      {state.variantPickerProduct && (
        <VariantSelector
          product={state.variantPickerProduct}
          onSelect={(productWithVariant) => {
            state.addProductToCart(productWithVariant);
            state.setVariantPickerProduct(null);
          }}
          onClose={() => state.setVariantPickerProduct(null)}
        />
      )}

      <ReceiptDialog
        sale={state.lastSale}
        open={state.showReceipt}
        onOpenChange={state.setShowReceipt}
      />

      {showCustomerForm && (
        <CustomerFormModal
          onSave={handleCustomerCreated}
          onClose={() => setShowCustomerForm(false)}
        />
      )}

      {/* Clear-cart confirmation. The original POS just nuked the cart on
          a single tap which made it terrifyingly easy to lose a half-built
          sale. */}
      <Dialog open={showClearConfirm} onOpenChange={setShowClearConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear the cart?</DialogTitle>
            <DialogDescription>
              This removes all {state.cart.length} line
              {state.cart.length === 1 ? '' : 's'} from the current sale. This
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowClearConfirm(false)}>
              Keep cart
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                state.clearCart();
                setShowClearConfirm(false);
                toast.info('Cart cleared');
              }}
            >
              Yes, clear
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <KeyboardShortcutsDialog open={showShortcuts} onOpenChange={setShowShortcuts} />
    </div>
  );
}

function KeyboardShortcutsDialog({ open, onOpenChange }) {
  const shortcuts = [
    { keys: ['F2'], label: 'Focus product search' },
    { keys: ['F4'], label: 'Focus amount received' },
    { keys: ['F9'], label: 'Complete sale' },
    { keys: ['Esc'], label: 'Close current dialog' },
    { keys: ['?'], label: 'Show this list' },
  ];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Power-user shortcuts for cashiers who keep their hands on the keyboard.
          </DialogDescription>
        </DialogHeader>
        <ul className="divide-y rounded-md border bg-card text-sm">
          {shortcuts.map((s) => (
            <li key={s.label} className="flex items-center justify-between px-3 py-2">
              <span>{s.label}</span>
              <span className="flex items-center gap-1">
                {s.keys.map((k) => (
                  <kbd
                    key={k}
                    className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded border bg-muted px-1.5 font-mono text-xs font-semibold"
                  >
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Got it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
