import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CATALOG_FETCH_PAGE_SIZE } from '../../../config/pagination';
import {
  productsAPI,
  categoriesAPI,
  customersAPI,
  salesAPI,
  authAPI,
} from '../../../services/api';
import { toast } from '../../../utils/toast';
import { isProductVariantsEnabled, normalizeProductForSale } from '../../../utils/moduleFeatures';
import { isProductOutOfStock } from '../../../utils/productStock';
import {
  posCartDraftKey,
  serializeRetailCartDraft,
  loadRetailCartDraft,
  saveRetailCartDraft,
  clearRetailCartDraft,
  localDraftNeedsRecoveryPrompt,
  countLocalDraftItems,
  resolveBranchIdFromUser,
} from '../../../utils/posCartRecovery';
import { useModuleSettings } from '../../../hooks/useModuleSettings';
import { paymentReferenceRequired } from '../../../utils/paymentMethods';
import {
  evaluatePosAmountReceived,
  isRegisteredPosCustomer,
} from '../../../utils/posCheckoutValidation';
import {
  salesShowDiscount,
  salesShowTax,
  salesShowDelivery,
  salesRequireCustomer,
  salesAllowPartialPayment,
  salesAllowExcessToWallet,
  salesValidateStock,
} from '../../../utils/salesDisplay';

/**
 * Cart-item identity.
 *
 * Two SaleItems for the same product but different variants are distinct
 * lines. Use this everywhere we look an item up or compare.
 */
export const cartItemKey = (item) =>
  item.variant_id ? `${item.id}-${item.variant_id}` : `${item.id}`;

/**
 * Resolve the *effective* stock cap for a cart line.
 *
 * Returns `null` when the item is not stock-tracked (e.g. a service product
 * with no quantity) — in that case the UI should not impose any cap.
 */
export const getLineStockCap = (item) => {
  if (item == null) return null;
  const raw = item.stock_quantity;
  if (raw === undefined || raw === null || raw === '') return null;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : null;
};

/**
 * usePOSState
 *
 * Owns every piece of POS state and the business logic that mutates it.
 * Returned as a flat bag so child components can pick what they need without
 * prop-drilling 35 props through 4 layers.
 *
 * What lives here:
 *  - data loads (products / categories / customers / user)
 *  - search + filter state with debounce
 *  - cart mutations (add / qty change / remove / clear)
 *  - totals (subtotal, discount, tax, delivery, total)
 *  - checkout: cash-tendered, payment method, partial/excess flows
 *  - sale submission with in-flight guard (double-submit protection)
 *
 * What does NOT live here:
 *  - UI/layout — that's POSPage and its children
 *  - one-off device tricks (fullscreen, system calculator) — those are
 *    component-local
 */
export function usePOSState() {
  const { settings: salesModuleSettings } = useModuleSettings('sales');
  const validateStock = salesValidateStock(salesModuleSettings);
  const requireCustomer = salesRequireCustomer(salesModuleSettings);
  const allowPartialPayment = salesAllowPartialPayment(salesModuleSettings);
  const allowExcessToWallet = salesAllowExcessToWallet(salesModuleSettings);

  const stockCapForItem = useCallback(
    (item) => (validateStock ? getLineStockCap(item) : null),
    [validateStock]
  );

  // --- Data ---
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // --- Filter / search ---
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);

  // --- Cart ---
  const [cart, setCart] = useState([]);

  // --- Customer ---
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  // --- Totals knobs ---
  const [taxPct, setTaxPct] = useState(0);          // VAT / sales-tax %
  const [discount, setDiscount] = useState(0);
  const [discountType, setDiscountType] = useState('percentage'); // 'percentage' | 'flat'
  const [deliveryEnabled, setDeliveryEnabled] = useState(false);
  const [deliveryMethod, setDeliveryMethod] = useState('pickup');
  const [deliveryCost, setDeliveryCost] = useState(0);
  const [shippingAddress, setShippingAddress] = useState('');

  // --- Checkout ---
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [receivedAmount, setReceivedAmount] = useState('');
  const [paymentReference, setPaymentReference] = useState('');
  const [submitting, setSubmitting] = useState(false);     // double-submit guard

  // --- Pending confirmation state (lifted so dialogs can read it) ---
  const [pendingSaleData, setPendingSaleData] = useState(null);
  const [showPartialPaymentConfirm, setShowPartialPaymentConfirm] = useState(false);
  const [showExcessPaymentConfirm, setShowExcessPaymentConfirm] = useState(false);

  // --- Receipt / success after sale ---
  const [lastSale, setLastSale] = useState(null);
  const [showReceipt, setShowReceipt] = useState(false);

  // --- Variant picker ---
  const [variantPickerProduct, setVariantPickerProduct] = useState(null);

  const [cartRecovery, setCartRecovery] = useState(null);
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const draftCheckedRef = useRef(false);

  // --- Bookkeeping ---
  const [orderNumber, setOrderNumber] = useState(
    () => `#ORD${Date.now().toString().slice(-6)}`
  );

  // Track the most-recent search/category state so a stale fetch can't
  // overwrite results from a fresher query.
  const requestSeqRef = useRef(0);

  // ------------------------------------------------------------------
  // Data loaders
  // ------------------------------------------------------------------

  const loadCategories = useCallback(async () => {
    try {
      const res = await categoriesAPI.list({ is_active: 'true' });
      const data = res.data.results || res.data || [];
      const organised = data
        .map((cat) => ({ ...cat, children: data.filter((c) => c.parent === cat.id) }))
        .filter((cat) => !cat.parent);
      setCategories(organised);
    } catch (e) {
      // Categories are non-fatal; the All tab still shows everything.
    }
  }, []);

  const loadProducts = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    setLoading(true);
    try {
      const params = { is_active: 'true', page_size: CATALOG_FETCH_PAGE_SIZE };
      if (selectedCategory !== 'all') params.category = selectedCategory;
      if (selectedSubcategory) params.subcategory = selectedSubcategory;
      if (searchQuery.trim()) params.search = searchQuery.trim();
      const res = await productsAPI.list(params);
      if (seq !== requestSeqRef.current) return;       // stale, ignore
      const data = res.data.results || res.data || [];
      const rows = Array.isArray(data) ? data : [];
      setProducts(rows.map((p) => normalizeProductForSale(p)));
    } catch (e) {
      if (seq === requestSeqRef.current) setProducts([]);
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, [selectedCategory, selectedSubcategory, searchQuery]);

  const loadCustomers = useCallback(async () => {
    try {
      const res = await customersAPI.list({ is_active: true, page_size: 1000 });
      const data = res.data.results || res.data || [];
      const list = Array.isArray(data) ? data : [];
      // A virtual walk-in customer keeps the UX simple (one customer field,
      // always populated) without polluting the customers table with a
      // synthetic row. Sale processing turns id==='walk-in' into null.
      const walkIn = { id: 'walk-in', name: 'Walk-in customer', customer_code: 'WALK-IN', is_active: true };
      if (requireCustomer) {
        setCustomers(list);
        setSelectedCustomer((prev) => (prev && prev.id !== 'walk-in' ? prev : null));
      } else {
        const merged = list.some((c) => c.id === 'walk-in') ? list : [walkIn, ...list];
        setCustomers(merged);
        setSelectedCustomer((prev) => prev || walkIn);
      }
    } catch (e) {
      const walkIn = { id: 'walk-in', name: 'Walk-in customer', customer_code: 'WALK-IN', is_active: true };
      if (requireCustomer) {
        setCustomers([]);
        setSelectedCustomer(null);
      } else {
        setCustomers([walkIn]);
        setSelectedCustomer((prev) => prev || walkIn);
      }
    }
  }, [requireCustomer]);

  const loadUser = useCallback(async () => {
    try {
      const stored = localStorage.getItem('user');
      if (stored) {
        setUser(JSON.parse(stored));
        return;
      }
      const res = await authAPI.me();
      setUser(res.data?.user || res.data);
    } catch (e) {
      setUser({ username: 'Admin' });
    }
  }, []);

  useEffect(() => {
    loadCategories();
    loadCustomers();
    loadUser();
  }, [loadCategories, loadCustomers, loadUser]);

  const cartDraftKey = useMemo(() => {
    if (!user?.id) return null;
    return posCartDraftKey(user.id, resolveBranchIdFromUser(user));
  }, [user]);

  useEffect(() => {
    if (!cartDraftKey || draftCheckedRef.current) return;
    draftCheckedRef.current = true;
    const draft = loadRetailCartDraft(cartDraftKey);
    if (localDraftNeedsRecoveryPrompt(draft)) {
      setCartRecovery({
        source: 'local',
        draft,
        itemCount: countLocalDraftItems(draft),
      });
    }
  }, [cartDraftKey]);

  useEffect(() => {
    if (!cartDraftKey || cartRecovery) return;
    if (cart.length === 0) {
      if (!draftCheckedRef.current) return;
      const pending = loadRetailCartDraft(cartDraftKey);
      if (pending && localDraftNeedsRecoveryPrompt(pending)) return;
      clearRetailCartDraft(cartDraftKey);
      return;
    }
    const timer = setTimeout(() => {
      saveRetailCartDraft(
        cartDraftKey,
        serializeRetailCartDraft({
          cart,
          selectedCustomer,
          taxPct,
          discount,
          discountType,
          paymentMethod,
        })
      );
    }, 450);
    return () => clearTimeout(timer);
  }, [
    cart,
    cartDraftKey,
    cartRecovery,
    selectedCustomer,
    taxPct,
    discount,
    discountType,
    paymentMethod,
  ]);

  const continueCartRecovery = useCallback(() => {
    const draft = cartRecovery?.draft;
    if (!draft) return;
    setRecoveryBusy(true);
    try {
      setCart(
        (draft.cart || []).map((line) =>
          normalizeProductForSale({
            ...line,
            price: parseFloat(line.price),
            quantity: Math.max(1, parseInt(line.quantity, 10) || 1),
          })
        )
      );
      setTaxPct(parseFloat(draft.taxPct) || 0);
      setDiscount(parseFloat(draft.discount) || 0);
      setDiscountType(draft.discountType === 'flat' ? 'flat' : 'percentage');
      if (draft.paymentMethod) setPaymentMethod(draft.paymentMethod);
      if (draft.selectedCustomer) {
        setSelectedCustomer((prev) => {
          if (draft.selectedCustomer.id === 'walk-in') {
            return (
              customers.find((c) => c.id === 'walk-in') || draft.selectedCustomer
            );
          }
          return (
            customers.find((c) => c.id === draft.selectedCustomer.id) ||
            draft.selectedCustomer
          );
        });
      }
      setCartRecovery(null);
    } finally {
      setRecoveryBusy(false);
    }
  }, [cartRecovery, customers]);

  const startNewSaleFromRecovery = useCallback(() => {
    setRecoveryBusy(true);
    try {
      if (cartDraftKey) clearRetailCartDraft(cartDraftKey);
      setCart([]);
      setCartRecovery(null);
      setReceivedAmount('');
      setDiscount(0);
      setTaxPct(0);
      setSelectedCustomer(
        customers.find((c) => c.id === 'walk-in') || {
          id: 'walk-in',
          name: 'Walk-in customer',
        }
      );
    } finally {
      setRecoveryBusy(false);
    }
  }, [cartDraftKey, customers]);

  // Debounced product reload on filter/search changes.
  useEffect(() => {
    const t = setTimeout(() => {
      loadProducts();
    }, 450);
    return () => clearTimeout(t);
  }, [loadProducts]);

  // ------------------------------------------------------------------
  // Cart mutations
  // ------------------------------------------------------------------

  const addProductToCart = useCallback((product) => {
    const key = cartItemKey(product);
    const qtyToAdd = product.quantity || 1;
    setCart((prev) => {
      const existing = prev.find((item) => cartItemKey(item) === key);
      if (existing) {
        const cap = stockCapForItem(existing);
        const requested = existing.quantity + qtyToAdd;
        const next = cap !== null ? Math.min(requested, cap) : requested;
        if (cap !== null && requested > cap) {
          toast.warning(
            `Only ${cap} ${existing.name} in stock — capped at the available quantity.`
          );
        }
        if (next === existing.quantity) return prev;
        return prev.map((item) =>
          cartItemKey(item) === key ? { ...item, quantity: next } : item
        );
      }
      const stock =
        product.stock_quantity !== undefined
          ? product.stock_quantity
          : product.variant?.stock_quantity ?? null;
      const newItem = {
        ...product,
        quantity: qtyToAdd,
        price: parseFloat(product.price),
        sku: product.sku || product.variant?.sku || '',
        stock_quantity: stock,
      };
      const cap = stockCapForItem(newItem);
      if (cap !== null && qtyToAdd > cap) {
        toast.warning(
          `Only ${cap} ${product.name} in stock — capped at the available quantity.`
        );
        newItem.quantity = Math.max(0, cap);
        if (newItem.quantity === 0) {
          toast.error(`${product.name} is out of stock.`);
          return prev;
        }
      }
      return [...prev, newItem];
    });
  }, []);

  const tryAddToCart = useCallback(
    (product) => {
      if (validateStock && isProductOutOfStock(product)) {
        toast.warning(`${product.name} is out of stock`);
        return;
      }
      const salePrice = parseFloat(product.price ?? product.selling_price ?? 0);
      if (!salePrice || salePrice <= 0) {
        toast.warning(`${product.name} has no selling price yet. Ask a manager to set pricing.`);
        return;
      }
      const hasSizes =
        (product.available_sizes_detail?.length || 0) > 0 ||
        (product.available_sizes?.length || 0) > 0;
      const hasColors =
        (product.available_colors_detail?.length || 0) > 0 ||
        (product.available_colors?.length || 0) > 0;
      if (
        isProductVariantsEnabled() &&
        product.has_variants &&
        (hasSizes || hasColors)
      ) {
        setVariantPickerProduct(product);
        return;
      }
      addProductToCart(normalizeProductForSale(product));
    },
    [addProductToCart, validateStock]
  );

  const setItemQuantity = useCallback((item, newQty) => {
    const requested = Math.max(0, parseInt(newQty, 10) || 0);
    if (requested === 0) {
      setCart((prev) => prev.filter((i) => cartItemKey(i) !== cartItemKey(item)));
      return;
    }
    setCart((prev) =>
      prev.map((i) => {
        if (cartItemKey(i) !== cartItemKey(item)) return i;
        const cap = stockCapForItem(i);
        const next = cap !== null ? Math.min(requested, cap) : requested;
        if (cap !== null && requested > cap) {
          toast.warning(`Only ${cap} in stock for ${i.name}.`);
        }
        return { ...i, quantity: next };
      })
    );
  }, []);

  const adjustItemQuantity = useCallback((item, delta) => {
    setCart((prev) => {
      const next = prev
        .map((i) => {
          if (cartItemKey(i) !== cartItemKey(item)) return i;
          const cap = stockCapForItem(i);
          const requested = i.quantity + delta;
          if (delta > 0 && cap !== null && requested > cap) {
            toast.warning(`Only ${cap} in stock for ${i.name}.`);
            return { ...i, quantity: cap };
          }
          return { ...i, quantity: Math.max(0, requested) };
        })
        .filter((i) => i.quantity > 0);
      return next;
    });
  }, []);

  const removeFromCart = useCallback((item) => {
    setCart((prev) => prev.filter((i) => cartItemKey(i) !== cartItemKey(item)));
  }, []);

  const clearCart = useCallback(() => {
    if (cartDraftKey) clearRetailCartDraft(cartDraftKey);
    setCart([]);
  }, [cartDraftKey]);

  // ------------------------------------------------------------------
  // Totals
  // ------------------------------------------------------------------

  const subtotal = useMemo(
    () => cart.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [cart]
  );

  const discountAmount = useMemo(() => {
    if (!salesShowDiscount(salesModuleSettings)) return 0;
    if (discountType === 'percentage') return (subtotal * discount) / 100;
    return Math.min(discount, subtotal);
  }, [subtotal, discount, discountType, salesModuleSettings]);

  const taxAmount = useMemo(() => {
    if (!salesShowTax(salesModuleSettings)) return 0;
    return (subtotal - discountAmount) * (taxPct / 100);
  }, [subtotal, discountAmount, taxPct, salesModuleSettings]);

  const total = useMemo(() => {
    const delivery = salesShowDelivery(salesModuleSettings) && deliveryEnabled ? deliveryCost : 0;
    return subtotal - discountAmount + taxAmount + delivery;
  }, [subtotal, discountAmount, taxAmount, deliveryEnabled, deliveryCost, salesModuleSettings]);

  const change = useMemo(() => {
    if (!['cash', 'mpesa'].includes(paymentMethod)) return 0;
    if (!receivedAmount) return 0;
    return Math.max(0, parseFloat(receivedAmount) - total);
  }, [paymentMethod, receivedAmount, total]);

  const cartItemCount = useMemo(
    () => cart.reduce((sum, item) => sum + item.quantity, 0),
    [cart]
  );

  /**
   * Any cart line whose qty exceeds its stock cap. With clamping in
   * setItemQuantity/adjustItemQuantity this should normally be empty, but
   * we still compute it as a defence-in-depth signal — e.g. if stock was
   * decremented in another tab while items were sitting in the cart, the
   * latest products payload (used by ProductGrid) will refresh and any
   * subsequent re-add will reveal the new cap.
   */
  const hasOversell = useMemo(
    () =>
      validateStock &&
      cart.some((item) => {
        const cap = stockCapForItem(item);
        return cap !== null && item.quantity > cap;
      }),
    [cart, validateStock, stockCapForItem]
  );

  // ------------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------------

  const resetAfterSale = useCallback(() => {
    if (cartDraftKey) clearRetailCartDraft(cartDraftKey);
    setCart([]);
    setReceivedAmount('');
    setPaymentReference('');
    setDiscount(0);
    setTaxPct(0);
    setDeliveryEnabled(false);
    setDeliveryMethod('pickup');
    setDeliveryCost(0);
    setShippingAddress('');
    setPendingSaleData(null);
    setShowPartialPaymentConfirm(false);
    setShowExcessPaymentConfirm(false);
    setOrderNumber(`#ORD${Date.now().toString().slice(-6)}`);
  }, [cartDraftKey]);

  const buildSalePayload = useCallback(
    ({ confirmedReceived, allowPartial, excessChoice }) => {
      const received =
        confirmedReceived !== undefined
          ? confirmedReceived
          : parseFloat(receivedAmount) || 0;

      const isTendered = paymentMethod === 'cash' || paymentMethod === 'mpesa';

      const formatAmountPaid = (amount) => {
        let v = Math.round(amount * 100) / 100;
        const max = 99999999.99;
        if (v > max) v = max;
        return parseFloat(v.toFixed(2));
      };

      return {
        items: cart.map((item) => ({
          product_id: item.id,
          variant_id: item.variant_id || null,
          quantity: item.quantity,
          unit_price: parseFloat(item.price),
        })),
        tax_amount: parseFloat(taxAmount.toFixed(2)),
        discount_amount: parseFloat(discountAmount.toFixed(2)),
        delivery_method: deliveryEnabled ? deliveryMethod : 'pickup',
        delivery_cost: parseFloat((deliveryEnabled ? deliveryCost : 0).toFixed(2)),
        shipping_address: deliveryEnabled && shippingAddress ? shippingAddress : null,
        payment_method: paymentMethod,
        payment_reference: paymentReferenceRequired(paymentMethod)
          ? String(paymentReference || '').trim()
          : '',
        amount_paid: isTendered ? formatAmountPaid(received) : formatAmountPaid(total),
        customer_id:
          selectedCustomer?.id && selectedCustomer.id !== 'walk-in'
            ? selectedCustomer.id
            : null,
        sale_type: 'pos',
        allow_partial_payment: !!allowPartial,
        excess_payment_choice: excessChoice || 'change',
      };
    },
    [
      cart,
      taxAmount,
      discountAmount,
      deliveryEnabled,
      deliveryMethod,
      deliveryCost,
      shippingAddress,
      paymentMethod,
      paymentReference,
      receivedAmount,
      selectedCustomer,
      total,
    ]
  );

  const submitSale = useCallback(
    async ({ allowPartial = false, excessChoice = 'change' } = {}) => {
      if (submitting) return;
      setSubmitting(true);
      try {
        const payload = buildSalePayload({
          confirmedReceived: pendingSaleData?.received,
          allowPartial,
          excessChoice,
        });
        const res = await salesAPI.create(payload);
        const backendTotal = parseFloat(res.data.total) || 0;
        const received =
          pendingSaleData?.received !== undefined
            ? pendingSaleData.received
            : parseFloat(receivedAmount) || 0;
        const calcChange =
          payload.payment_method === 'cash' || payload.payment_method === 'mpesa'
            ? excessChoice === 'wallet'
              ? 0
              : Math.max(0, received - backendTotal)
            : 0;

        const sale = { ...res.data, change: calcChange };
        setLastSale(sale);
        setShowReceipt(true);
        resetAfterSale();

        if (allowPartial && pendingSaleData?.balance > 0) {
          toast.success('Sale completed. Balance added to customer account.');
        } else if (excessChoice === 'wallet' && pendingSaleData?.excess > 0) {
          toast.success("Sale completed. Excess credited to customer's wallet.");
        } else {
          toast.success('Sale completed');
        }
      } catch (err) {
        toast.error(
          'Sale failed: ' + (err.response?.data?.error || err.message || 'unknown error')
        );
      } finally {
        setSubmitting(false);
      }
    },
    [submitting, buildSalePayload, pendingSaleData, receivedAmount, resetAfterSale]
  );

  /**
   * Click handler for the Pay button. Routes through the partial-payment /
   * excess-payment confirmations when needed, otherwise submits directly.
   *
   * Pre-flight validation is intentionally permissive — the backend's
   * `validate_sale_items` is authoritative. Frontend just blocks the most
   * common cashier mistakes.
   */
  const requestPayment = useCallback(() => {
    if (submitting) return;
    if (cart.length === 0) {
      toast.warning('Cart is empty');
      return;
    }
    if (requireCustomer && (!selectedCustomer || selectedCustomer.id === 'walk-in')) {
      toast.warning('Select a registered customer before completing this sale.');
      return;
    }
    if (hasOversell) {
      toast.error(
        'One or more items exceed available stock. Adjust quantities before completing the sale.'
      );
      return;
    }

    if (paymentReferenceRequired(paymentMethod) && !String(paymentReference || '').trim()) {
      toast.warning('Enter the payment reference (e.g. M-Pesa code or card details).');
      return;
    }

    const isTendered = paymentMethod === 'cash' || paymentMethod === 'mpesa';
    const receivedCheck = evaluatePosAmountReceived(receivedAmount, {
      allowPartialPayment,
      hasRegisteredCustomer: isRegisteredPosCustomer(selectedCustomer),
    });

    if (isTendered) {
      if (!receivedCheck.ok) {
        toast.warning(receivedCheck.message);
        return;
      }
      const received = receivedCheck.received;

      if (receivedCheck.creditSale || received < total) {
        if (!allowPartialPayment) {
          toast.warning('Partial payment is disabled. Collect the full amount to continue.');
          return;
        }
        if (!isRegisteredPosCustomer(selectedCustomer)) {
          toast.warning(
            'Pick a registered customer before allowing a partial payment — the balance is recorded against their account.'
          );
          return;
        }
        setPendingSaleData({ total, received, balance: total - received });
        setShowPartialPaymentConfirm(true);
        return;
      }

      if (received > total && selectedCustomer && selectedCustomer.id !== 'walk-in') {
        if (allowExcessToWallet) {
          setPendingSaleData({ total, received, excess: received - total });
          setShowExcessPaymentConfirm(true);
          return;
        }
        submitSale({ allowPartial: false, excessChoice: 'change' });
        return;
      }
    }

    submitSale({ allowPartial: false, excessChoice: 'change' });
  }, [
    submitting,
    cart.length,
    requireCustomer,
    hasOversell,
    paymentMethod,
    paymentReference,
    receivedAmount,
    total,
    selectedCustomer,
    allowPartialPayment,
    allowExcessToWallet,
    submitSale,
  ]);

  return {
    // data
    products,
    categories,
    customers,
    user,
    loading,
    orderNumber,

    // filters
    searchQuery, setSearchQuery,
    selectedCategory, setSelectedCategory,
    selectedSubcategory, setSelectedSubcategory,

    // cart
    cart,
    cartItemCount,
    hasOversell,
    tryAddToCart,
    addProductToCart,
    setItemQuantity,
    adjustItemQuantity,
    removeFromCart,
    clearCart,

    // customer
    selectedCustomer, setSelectedCustomer,
    setCustomers,
    requireCustomer,
    allowPartialPayment,
    allowExcessToWallet,
    validateStock,
    salesModuleSettings,

    // totals & knobs
    taxPct, setTaxPct,
    discount, setDiscount,
    discountType, setDiscountType,
    deliveryEnabled, setDeliveryEnabled,
    deliveryMethod, setDeliveryMethod,
    deliveryCost, setDeliveryCost,
    shippingAddress, setShippingAddress,
    subtotal,
    discountAmount,
    taxAmount,
    total,
    change,

    // checkout
    paymentMethod, setPaymentMethod,
    receivedAmount, setReceivedAmount,
    paymentReference, setPaymentReference,
    submitting,
    requestPayment,
    submitSale,

    // confirmation flow
    pendingSaleData,
    showPartialPaymentConfirm, setShowPartialPaymentConfirm,
    showExcessPaymentConfirm, setShowExcessPaymentConfirm,

    // receipt
    lastSale,
    showReceipt, setShowReceipt,

    // variant picker
    variantPickerProduct, setVariantPickerProduct,

    cartRecovery,
    recoveryBusy,
    continueCartRecovery,
    startNewSaleFromRecovery,

    // reloads
    reloadProducts: loadProducts,
    reloadCustomers: loadCustomers,
  };
}
