import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  productsAPI,
  customersAPI,
  salesAPI,
} from '../../../services/api';
import { toast } from '../../../utils/toast';
import { cartItemKey, getLineStockCap } from '../v2/usePOSState';
import { isProductVariantsEnabled, normalizeProductForSale } from '../../../utils/moduleFeatures';
import { isProductOutOfStock } from '../../../utils/productStock';
import { formatApiError } from '../../../utils/apiErrors';
import {
  WALK_IN_CUSTOMER,
  mergeCustomersWithWalkIn,
  isWalkInCustomer,
  customerIdForSale,
} from '../../../utils/walkInCustomer';
import { useModuleSettings } from '../../../hooks/useModuleSettings';
import {
  salesShowDiscount,
  salesShowTax,
  salesRequireCustomer,
  salesAllowPartialPayment,
  salesValidateStock,
} from '../../../utils/salesDisplay';
import { buildBillingCartLine } from '../../../utils/billingCartLine';
import {
  shouldPromptForHoldingRecovery,
  countHoldingItems,
} from '../../../utils/posCartRecovery';
import { evaluatePartialPaymentToggle } from '../../../utils/billingPartialPayment';
import { paymentReferenceRequired } from '../../../utils/paymentMethods';

const HOLDING_SYNC_MS = 600;

/** Clamp line quantity to on-hand stock when the product tracks stock. */
function applyStockCapToLine(line, validateStock = true) {
  const cap = validateStock ? getLineStockCap(line) : null;
  if (cap === null) return line;
  if (line.quantity > cap) {
    return { ...line, quantity: Math.max(0, cap) };
  }
  return line;
}

function holdingItemToCartLine(item) {
  const product = item.product || {};
  const line = normalizeProductForSale({
    id: product.id || item.product_id,
    name: item.product_name || product.name || 'Product',
    sku: item.product_sku || product.sku,
    price: parseFloat(item.unit_price),
    cost: parseFloat(product.cost || 0),
    stock_quantity: product.stock_quantity,
    track_stock: product.track_stock !== false,
    has_variants: product.has_variants,
    variants: product.variants,
  });
  const selling = parseFloat(item.unit_price);
  const mrp = parseFloat(item.product?.mrp) || selling;
  return applyStockCapToLine({
    ...line,
    variant_id: item.variant?.id || item.variant_id || null,
    mrp,
    selling_price: selling,
    price: selling,
  });
}

export function useBillingPOSState() {
  const { settings: salesModuleSettings } = useModuleSettings('sales');
  const validateStock = salesValidateStock(salesModuleSettings);
  const requireCustomer = salesRequireCustomer(salesModuleSettings);
  const allowPartialPayment = salesAllowPartialPayment(salesModuleSettings);
  const showDiscount = salesShowDiscount(salesModuleSettings);
  const showTax = salesShowTax(salesModuleSettings);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [cart, setCart] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerQuery, setCustomerQuery] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(WALK_IN_CUSTOMER);

  const [holdingId, setHoldingId] = useState(null);
  const [holdingNumber, setHoldingNumber] = useState('');
  const [syncingHolding, setSyncingHolding] = useState(false);
  const [loadingHolding, setLoadingHolding] = useState(true);
  const [cartRecovery, setCartRecovery] = useState(null);
  const [recoveryBusy, setRecoveryBusy] = useState(false);

  const [taxPct, setTaxPct] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [discountType, setDiscountType] = useState('flat'); // flat | percentage
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentReference, setPaymentReference] = useState('');
  const [partialPayment, setPartialPayment] = useState(false);
  const [partialPaymentCustomerPrompt, setPartialPaymentCustomerPrompt] = useState(false);
  const [amountPaid, setAmountPaid] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [lastSale, setLastSale] = useState(null);
  const [showReceipt, setShowReceipt] = useState(false);
  const [variantPickerProduct, setVariantPickerProduct] = useState(null);

  const syncTimerRef = useRef(null);
  const skipNextSyncRef = useRef(false);

  const subtotal = useMemo(
    () => cart.reduce((s, i) => s + i.price * i.quantity, 0),
    [cart]
  );

  const discountAmount = useMemo(() => {
    if (!showDiscount) return 0;
    const d = parseFloat(discount) || 0;
    if (discountType === 'percentage') {
      return Math.min(subtotal, (subtotal * d) / 100);
    }
    return Math.min(subtotal, d);
  }, [discount, discountType, subtotal, showDiscount]);

  const taxableValue = useMemo(
    () => Math.max(0, subtotal - discountAmount),
    [subtotal, discountAmount]
  );

  const taxAmount = useMemo(() => {
    if (!showTax) return 0;
    return (taxableValue * (parseFloat(taxPct) || 0)) / 100;
  }, [taxableValue, taxPct, showTax]);

  const total = useMemo(
    () => taxableValue + taxAmount,
    [taxableValue, taxAmount]
  );

  const itemCount = useMemo(
    () => cart.reduce((n, i) => n + i.quantity, 0),
    [cart]
  );

  const loadCustomers = useCallback(async () => {
    try {
      const res = await customersAPI.list({ is_active: true, page_size: 500 });
      const data = res.data.results || res.data || [];
      if (requireCustomer) {
        setCustomers(data);
        setSelectedCustomer((prev) => (prev && !isWalkInCustomer(prev) ? prev : null));
      } else {
        setCustomers(mergeCustomersWithWalkIn(data));
      }
    } catch {
      setCustomers(requireCustomer ? [] : [WALK_IN_CUSTOMER]);
    }
  }, [requireCustomer]);

  const selectWalkInCustomer = useCallback(() => {
    setSelectedCustomer(WALK_IN_CUSTOMER);
    setCustomerQuery('');
    setPartialPayment(false);
  }, []);

  useEffect(() => {
    if (partialPayment && isWalkInCustomer(selectedCustomer)) {
      setPartialPayment(false);
    }
  }, [selectedCustomer, partialPayment]);

  const attemptSetPartialPayment = useCallback((checked) => {
    const { allow } = evaluatePartialPaymentToggle(checked, selectedCustomer);
    if (allow) {
      setPartialPayment(checked);
      if (!checked) setPartialPaymentCustomerPrompt(false);
      return true;
    }
    setPartialPaymentCustomerPrompt(true);
    return false;
  }, [selectedCustomer]);

  const closePartialPaymentCustomerPrompt = useCallback(() => {
    setPartialPaymentCustomerPrompt(false);
  }, []);

  const hydrateFromHolding = useCallback((holding) => {
    if (!holding) return;
    setHoldingId(holding.id);
    setHoldingNumber(holding.sale_number);
    setTaxPct(
      holding.subtotal > 0
        ? ((parseFloat(holding.tax_amount) || 0) / parseFloat(holding.subtotal)) * 100
        : 0
    );
    setDiscount(parseFloat(holding.discount_amount) || 0);
    setDiscountType('flat');

    const lines = (holding.items || []).map(holdingItemToCartLine).filter((l) => l.quantity > 0);
    setCart(lines);

    if (holding.customer) {
      setSelectedCustomer(
        customers.find((c) => c.id === holding.customer) || {
          id: holding.customer,
          name: holding.customer_name || 'Customer',
        }
      );
    } else {
      setSelectedCustomer(WALK_IN_CUSTOMER);
    }
  }, [customers]);

  const loadActiveHolding = useCallback(async () => {
    setLoadingHolding(true);
    try {
      const res = await salesAPI.activeHolding();
      const holding = res.data?.holding;
      if (shouldPromptForHoldingRecovery(holding)) {
        setCartRecovery({
          source: 'holding',
          holding,
          itemCount: countHoldingItems(holding),
          label: holding.sale_number,
        });
        return;
      }
      if (holding?.items?.length) {
        skipNextSyncRef.current = true;
        hydrateFromHolding(holding);
      } else if (holding) {
        setHoldingId(holding.id);
        setHoldingNumber(holding.sale_number);
      }
    } catch {
      // No holding yet — normal for a fresh session.
    } finally {
      setLoadingHolding(false);
    }
  }, [hydrateFromHolding]);

  const continueCartRecovery = useCallback(() => {
    if (!cartRecovery?.holding) return;
    setRecoveryBusy(true);
    try {
      skipNextSyncRef.current = true;
      hydrateFromHolding(cartRecovery.holding);
      setCartRecovery(null);
    } finally {
      setRecoveryBusy(false);
    }
  }, [cartRecovery, hydrateFromHolding]);

  const startNewSaleFromRecovery = useCallback(async () => {
    setRecoveryBusy(true);
    try {
      const holding = cartRecovery?.holding;
      if (holding?.id) {
        try {
          await salesAPI.cancelHolding(holding.id);
        } catch {
          /* best effort */
        }
      }
      setCart([]);
      setHoldingId(null);
      setHoldingNumber('');
      setCartRecovery(null);
      setSelectedCustomer(WALK_IN_CUSTOMER);
      setCustomerQuery('');
    } finally {
      setRecoveryBusy(false);
    }
  }, [cartRecovery]);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

  useEffect(() => {
    if (customers.length) loadActiveHolding();
  }, [customers.length, loadActiveHolding]);

  const searchProducts = useCallback(async (q) => {
    const term = q.trim();
    if (!term) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const res = await productsAPI.list({ search: term, is_active: 'true', page_size: 10 });
      const data = res.data.results || res.data || [];
      const rows = Array.isArray(data) ? data : [];
      setSearchResults(rows.map((p) => normalizeProductForSale(p)));
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => searchProducts(searchQuery), 280);
    return () => clearTimeout(t);
  }, [searchQuery, searchProducts]);

  const buildHoldingPayload = useCallback(
    () => ({
      holding_id: holdingId,
      items: cart.map((item) => ({
        product_id: item.id,
        variant_id: item.variant_id || null,
        quantity: item.quantity,
        unit_price: parseFloat(item.price),
      })),
      customer_id: customerIdForSale(selectedCustomer),
      tax_amount: parseFloat(taxAmount.toFixed(2)),
      discount_amount: parseFloat(discountAmount.toFixed(2)),
    }),
    [holdingId, cart, selectedCustomer, taxAmount, discountAmount]
  );

  const syncHolding = useCallback(async () => {
    if (skipNextSyncRef.current) {
      skipNextSyncRef.current = false;
      return;
    }
    setSyncingHolding(true);
    try {
      const res = await salesAPI.saveHolding(buildHoldingPayload());
      setHoldingId(res.data.id);
      setHoldingNumber(res.data.sale_number);
    } catch (err) {
      toast.error(formatApiError(err, 'Could not save draft invoice'));
    } finally {
      setSyncingHolding(false);
    }
  }, [buildHoldingPayload]);

  useEffect(() => {
    if (loadingHolding || cartRecovery) return;
    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    syncTimerRef.current = setTimeout(() => {
      if (cart.length === 0 && !holdingId) return;
      syncHolding();
    }, HOLDING_SYNC_MS);
    return () => {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    };
  }, [cart, selectedCustomer, taxAmount, discountAmount, loadingHolding, holdingId, cartRecovery, syncHolding]);

  const addToCart = useCallback((product, variant = null) => {
    if (validateStock && isProductOutOfStock(product)) {
      toast.warning(`${product.name} is out of stock`);
      return;
    }
    if (isProductVariantsEnabled() && product.has_variants && !variant) {
      const hasSizes =
        (product.available_sizes_detail?.length || 0) > 0 ||
        (product.available_sizes?.length || 0) > 0;
      const hasColors =
        (product.available_colors_detail?.length || 0) > 0 ||
        (product.available_colors?.length || 0) > 0;
      if (hasSizes || hasColors) {
        setVariantPickerProduct(product);
        return;
      }
    }
    const base = normalizeProductForSale(product);
    const draft = buildBillingCartLine(base, variant, { validateStock });
    const line = {
      id: draft.id,
      name: draft.name,
      sku: draft.sku,
      mrp: draft.mrp,
      selling_price: draft.selling_price,
      price: draft.price,
      cost: draft.cost,
      quantity: draft.quantity,
      variant_id: isProductVariantsEnabled() ? draft.variant_id : null,
      stock_quantity: draft.stock_quantity,
      track_stock: draft.track_stock,
      has_variants: isProductVariantsEnabled() ? draft.has_variants : false,
    };
    const stockCap = validateStock ? getLineStockCap(line) : null;

    setCart((prev) => {
      const key = cartItemKey(line);
      const idx = prev.findIndex((i) => cartItemKey(i) === key);
      if (idx >= 0) {
        const next = [...prev];
        const cap = validateStock ? getLineStockCap(next[idx]) : null;
        const newQty = next[idx].quantity + 1;
        if (cap !== null && newQty > cap) {
          toast.warning(`Only ${cap} in stock`);
          return prev;
        }
        next[idx] = applyStockCapToLine({ ...next[idx], quantity: newQty }, validateStock);
        return next;
      }
      if (stockCap !== null && stockCap < 1) {
        toast.warning('Out of stock');
        return prev;
      }
      return [...prev, applyStockCapToLine(line, validateStock)];
    });
    setSearchQuery('');
    setSearchResults([]);
  }, [validateStock]);

  const updateQty = useCallback((key, delta) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (cartItemKey(item) !== key) return item;
          const cap = validateStock ? getLineStockCap(item) : null;
          const nextQty = item.quantity + delta;
          if (nextQty <= 0) return null;
          if (cap !== null && nextQty > cap) {
            toast.warning(`Only ${cap} in stock for ${item.name}`);
            return item;
          }
          return applyStockCapToLine({ ...item, quantity: nextQty }, validateStock);
        })
        .filter(Boolean)
    );
  }, [validateStock]);

  const setQty = useCallback((key, newQty) => {
    const requested = Math.max(0, parseInt(newQty, 10) || 0);
    if (requested === 0) {
      setCart((prev) => prev.filter((i) => cartItemKey(i) !== key));
      return;
    }
    setCart((prev) =>
      prev.map((item) => {
        if (cartItemKey(item) !== key) return item;
        return applyStockCapToLine({ ...item, quantity: requested }, validateStock);
      })
    );
  }, [validateStock]);

  const removeLine = useCallback((key) => {
    setCart((prev) => prev.filter((i) => cartItemKey(i) !== key));
  }, []);

  const clearCart = useCallback(async () => {
    if (holdingId) {
      try {
        await salesAPI.cancelHolding(holdingId);
      } catch {
        /* best effort */
      }
    }
    setCart([]);
    setHoldingId(null);
    setHoldingNumber('');
    setAmountPaid('');
    setSelectedCustomer(WALK_IN_CUSTOMER);
    setCustomerQuery('');
  }, [holdingId]);

  const checkout = useCallback(async () => {
    if (submitting) return;
    if (cart.length === 0) {
      toast.warning('Add at least one item');
      return;
    }

    let id = holdingId;
    if (!id) {
      try {
        const res = await salesAPI.saveHolding(buildHoldingPayload());
        id = res.data.id;
        setHoldingId(id);
        setHoldingNumber(res.data.sale_number);
      } catch (err) {
        toast.error(formatApiError(err, 'Could not create draft invoice'));
        return;
      }
    } else {
      try {
        await salesAPI.saveHolding(buildHoldingPayload());
      } catch (err) {
        toast.error(formatApiError(err, 'Could not update draft invoice'));
        return;
      }
    }

    const paid = parseFloat(amountPaid) || 0;
    if (paymentReferenceRequired(paymentMethod) && !String(paymentReference || '').trim()) {
      toast.warning('Enter the payment reference (e.g. M-Pesa code or card details).');
      return;
    }
    if (paymentMethod !== 'other' && paid <= 0) {
      toast.warning('Enter amount received');
      return;
    }
    if (requireCustomer && (!selectedCustomer || isWalkInCustomer(selectedCustomer))) {
      toast.warning('Select a registered customer to complete this sale.');
      return;
    }
    if (partialPayment) {
      if (!allowPartialPayment) {
        toast.warning('Partial payment is disabled in store settings.');
        return;
      }
      if (isWalkInCustomer(selectedCustomer)) {
        toast.warning('Select a registered customer to record a balance on account.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const res = await salesAPI.checkout(id, {
        payment_method: paymentMethod,
        payment_reference: paymentReferenceRequired(paymentMethod)
          ? String(paymentReference || '').trim()
          : '',
        amount_paid: paymentMethod === 'other' ? total : paid,
        allow_partial_payment: partialPayment,
        excess_payment_choice: 'change',
      });
      const sale = {
        ...res.data,
        change: Math.max(0, paid - parseFloat(res.data.total)),
      };
      setLastSale(sale);
      setShowReceipt(true);
      setCart([]);
      setHoldingId(null);
      setHoldingNumber('');
      setAmountPaid('');
      setPaymentReference('');
      setDiscount(0);
      setTaxPct(0);
      setSelectedCustomer(WALK_IN_CUSTOMER);
      setCustomerQuery('');
      toast.success('Sale completed');
    } catch (err) {
      const msg = formatApiError(err, 'Checkout failed');
      toast.error(msg);
      if (err.response?.status === 404) {
        setHoldingId(null);
        setHoldingNumber('');
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    submitting,
    cart.length,
    holdingId,
    buildHoldingPayload,
    amountPaid,
    paymentReference,
    paymentMethod,
    partialPayment,
    allowPartialPayment,
    requireCustomer,
    selectedCustomer,
    total,
  ]);

  const filteredCustomers = useMemo(() => {
    const q = customerQuery.trim().toLowerCase();
    const registered = customers.filter((c) => !isWalkInCustomer(c));
    if (!q) return registered.slice(0, 8);
    return registered
      .filter(
        (c) =>
          c.name?.toLowerCase().includes(q) ||
          c.phone?.includes(q) ||
          c.customer_code?.toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [customers, customerQuery]);

  return {
    searchQuery,
    setSearchQuery,
    searchResults,
    searching,
    cart,
    itemCount,
    subtotal,
    discountAmount,
    taxableValue,
    taxAmount,
    total,
    taxPct,
    setTaxPct,
    discount,
    setDiscount,
    discountType,
    setDiscountType,
    paymentMethod,
    setPaymentMethod,
    partialPayment,
    setPartialPayment,
    attemptSetPartialPayment,
    partialPaymentCustomerPrompt,
    closePartialPaymentCustomerPrompt,
    amountPaid,
    setAmountPaid,
    paymentReference,
    setPaymentReference,
    selectedCustomer,
    setSelectedCustomer,
    selectWalkInCustomer,
    loadCustomers,
    isWalkInCustomer,
    customerQuery,
    setCustomerQuery,
    filteredCustomers,
    holdingNumber,
    syncingHolding,
    loadingHolding,
    submitting,
    addToCart,
    updateQty,
    setQty,
    removeLine,
    clearCart,
    checkout,
    variantPickerProduct,
    setVariantPickerProduct,
    lastSale,
    showReceipt,
    setShowReceipt,
    showDiscount,
    showTax,
    allowPartialPayment,
    requireCustomer,
    validateStock,
    cartRecovery,
    recoveryBusy,
    continueCartRecovery,
    startNewSaleFromRecovery,
  };
}
