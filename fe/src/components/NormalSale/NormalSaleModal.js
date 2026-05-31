import React, { useState, useEffect } from 'react';
import { productsAPI, customersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import VariantSelector from '../POS/VariantSelector';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import CustomerFormModal from '../Customers/CustomerFormModal';
import { toast } from '../../utils/toast';
import { cn } from '../../lib/cn';
import { Button } from '../ui/button';

const NormalSaleModal = ({ isOpen, onClose, onSave }) => {
  const [customers, setCustomers] = useState([]);
  const [filteredCustomers, setFilteredCustomers] = useState([]);
  const [customerSearch, setCustomerSearch] = useState('');
  const [showCustomerSearch, setShowCustomerSearch] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [saleDate, setSaleDate] = useState(new Date().toISOString().split('T')[0]);
  const [orderTax, setOrderTax] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [shipping, setShipping] = useState(0);
  const [deliveryMethod, setDeliveryMethod] = useState('pickup');
  const [shippingAddress, setShippingAddress] = useState('');
  const [shippingLocation, setShippingLocation] = useState('');
  const [status, setStatus] = useState('pending');
  const [productRows, setProductRows] = useState([]);
  const [productSearch, setProductSearch] = useState('');
  const [productSearchResults, setProductSearchResults] = useState([]);
  const [showProductSearch, setShowProductSearch] = useState(false);
  const [selectedProductRowIndex, setSelectedProductRowIndex] = useState(null);
  const [showVariantSelector, setShowVariantSelector] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [paymentType, setPaymentType] = useState('pay_now'); // 'pay_now' or 'installments'
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [amountPaid, setAmountPaid] = useState(0);
  const [amountPaidManuallySet, setAmountPaidManuallySet] = useState(false);
  const [useWallet, setUseWallet] = useState(false);
  const [walletAmount, setWalletAmount] = useState(0);
  const [paymentPlanData, setPaymentPlanData] = useState({
    number_of_installments: 1,
    frequency: 'monthly',
    start_date: '',
  });
  const [showPartialPaymentConfirm, setShowPartialPaymentConfirm] = useState(false);
  const [showExcessPaymentConfirm, setShowExcessPaymentConfirm] = useState(false);
  const [pendingSaleData, setPendingSaleData] = useState(null);
  const [excessPaymentChoice, setExcessPaymentChoice] = useState('change'); // 'change' or 'wallet'
  const [showCustomerFormModal, setShowCustomerFormModal] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadCustomers();
      // Don't add initial empty row - let user search and add products
      setProductRows([]);
      setCustomerSearch('');
      setSelectedCustomer(null);
      setProductSearch('');
      setProductSearchResults([]);
      setShowProductSearch(false);
      setShowCustomerSearch(false);
      setUseWallet(false);
      setWalletAmount(0);
    }
  }, [isOpen]);

  // Refresh customers when window regains focus (in case user added a customer in another tab)
  useEffect(() => {
    if (!isOpen) return;
    
    const handleFocus = () => {
      loadCustomers();
    };
    
    // Also refresh on visibility change (when tab becomes visible)
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadCustomers();
      }
    };
    
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isOpen]);

  useEffect(() => {
    // Filter customers based on search
    if (customerSearch.trim()) {
      const searchLower = customerSearch.toLowerCase();
      const filtered = customers.filter(customer => 
        customer.name.toLowerCase().includes(searchLower) ||
        customer.customer_code?.toLowerCase().includes(searchLower) ||
        customer.phone?.includes(customerSearch) ||
        customer.email?.toLowerCase().includes(searchLower)
      );
      setFilteredCustomers(filtered);
      setShowCustomerSearch(true);
    } else {
      // Show all customers when search is empty
      setFilteredCustomers(customers);
      setShowCustomerSearch(false);
    }
  }, [customerSearch, customers]);

  // Auto-update amount paid when grand total changes (for pay now)
  // Only update if user hasn't manually changed it
  useEffect(() => {
    if (paymentType === 'pay_now' && isOpen && !amountPaidManuallySet) {
      // Calculate totals inline to avoid dependency issues
      const validRows = productRows.filter(row => row.product_id);
      const subtotal = validRows.reduce((sum, row) => sum + (row.quantity * row.unit_price), 0);
      const totalDiscount = validRows.reduce((sum, row) => sum + row.discount, 0) + parseFloat(discount || 0);
      const totalTax = validRows.reduce((sum, row) => sum + row.tax_amount, 0) + parseFloat(orderTax || 0);
      const grandTotal = subtotal - totalDiscount + totalTax + parseFloat(shipping || 0);
      
      if (grandTotal > 0) {
        setAmountPaid(grandTotal);
      }
    }
  }, [productRows, discount, orderTax, shipping, paymentType, isOpen, amountPaidManuallySet]);

  const loadCustomers = async () => {
    try {
      // Fetch all customers with large page size to ensure newly added customers are included
      const response = await customersAPI.list({ is_active: true, page_size: 1000 });
      const customersData = response.data.results || response.data || [];
      setCustomers(Array.isArray(customersData) ? customersData : []);
    } catch (error) {
      console.error('Error loading customers:', error);
      setCustomers([]);
    }
  };

  const searchProducts = async (query) => {
    const trimmedQuery = query?.trim();
    if (!trimmedQuery || trimmedQuery.length < 1) {
      setProductSearchResults([]);
      setShowProductSearch(false);
      return;
    }

    try {
      const response = await productsAPI.search(trimmedQuery, 20); // Increased to 20 results
      const products = response.data || [];
      setProductSearchResults(products);
      setShowProductSearch(products.length > 0);
    } catch (error) {
      console.error('Error searching products:', error);
      setProductSearchResults([]);
      setShowProductSearch(false);
    }
  };

  const handleProductSearchChange = (e) => {
    const value = e.target.value;
    setProductSearch(value);
    // Debounce search for better performance
    if (value.trim().length >= 1) {
      searchProducts(value);
    } else {
      setProductSearchResults([]);
      setShowProductSearch(false);
    }
  };

  const handleProductSelect = async (product) => {
    // Check if product has variants
    const hasSizes = (product.available_sizes_detail && product.available_sizes_detail.length > 0) || 
                     (product.available_sizes && product.available_sizes.length > 0);
    const hasColors = (product.available_colors_detail && product.available_colors_detail.length > 0) || 
                      (product.available_colors && product.available_colors.length > 0);
    
    if (product.has_variants && (hasSizes || hasColors)) {
      // Create a new row for this product
      const newRowIndex = productRows.length;
      addProductRow(); // Add empty row first
      setSelectedProduct(product);
      setSelectedProductRowIndex(newRowIndex);
      setShowVariantSelector(true);
      setShowProductSearch(false);
      setProductSearch(''); // Clear search
      return;
    }

    // Add product without variant - automatically create new row
    const newRowIndex = productRows.length;
    addProductRow(); // Add new row
    addProductToRow(product, newRowIndex);
    setShowProductSearch(false);
    // Clear search immediately to allow user to search for next product
    setProductSearch('');
  };

  const addProductToRow = (product, rowIndex, variant = null) => {
    const unitPrice = variant 
      ? parseFloat(variant.effective_price || variant.price || product.price)
      : parseFloat(product.price);
    
    const unitCost = variant
      ? parseFloat(variant.cost || product.cost || 0)
      : parseFloat(product.cost || 0);

    const newRow = {
      product_id: product.id,
      product_name: product.name,
      product_sku: variant ? (variant.sku || product.sku) : product.sku,
      variant_id: variant ? variant.id : null,
      variant: variant,
      size: variant ? variant.size_name : null,
      color: variant ? variant.color_name : null,
      quantity: 1,
      unit_price: unitPrice,
      unit_cost: unitCost,
      discount: 0,
      tax_percent: 0,
      tax_amount: 0,
      total_cost: unitPrice,
    };

    const updatedRows = [...productRows];
    // Ensure row exists (in case it was removed)
    if (rowIndex >= updatedRows.length) {
      // Add empty rows if needed
      while (updatedRows.length <= rowIndex) {
        updatedRows.push({
          product_id: null,
          product_name: '',
          product_sku: '',
          variant_id: null,
          quantity: 1,
          unit_price: 0,
          unit_cost: 0,
          discount: 0,
          tax_percent: 0,
          tax_amount: 0,
          total_cost: 0,
        });
      }
    }
    updatedRows[rowIndex] = newRow;
    setProductRows(updatedRows);
    // Show success message
    const variantInfo = variant ? ` (${variant.size_name || ''}${variant.size_name && variant.color_name ? ', ' : ''}${variant.color_name || ''})` : '';
    toast.success(`${product.name}${variantInfo} added to sale`);
  };

  const addProductRow = () => {
    setProductRows([...productRows, {
      product_id: null,
      product_name: '',
      product_sku: '',
      variant_id: null,
      quantity: 1,
      unit_price: 0,
      unit_cost: 0,
      discount: 0,
      tax_percent: 0,
      tax_amount: 0,
      total_cost: 0,
    }]);
  };

  const removeProductRow = (index) => {
    if (!productRows[index]?.product_id) {
      // If row is empty, just remove it silently
      const updatedRows = productRows.filter((_, i) => i !== index);
      setProductRows(updatedRows);
      return;
    }
    
    // Remove product (no confirmation needed for better UX)
    const productName = productRows[index].product_name;
    const updatedRows = productRows.filter((_, i) => i !== index);
    setProductRows(updatedRows);
    toast.success(`${productName} removed from sale`);
  };

  const updateProductRow = (index, field, value) => {
    const updatedRows = [...productRows];
    const row = updatedRows[index];
    
    if (field === 'quantity' || field === 'unit_price' || field === 'discount' || field === 'tax_percent') {
      row[field] = parseFloat(value) || 0;
      
      // Recalculate tax amount and total cost
      const subtotal = (row.quantity * row.unit_price) - row.discount;
      row.tax_amount = (subtotal * row.tax_percent) / 100;
      row.total_cost = subtotal + row.tax_amount;
    } else {
      row[field] = value;
    }
    
    setProductRows(updatedRows);
  };

  const calculateTotals = () => {
    // Only calculate from rows with products
    const validRows = productRows.filter(row => row.product_id);
    const subtotal = validRows.reduce((sum, row) => sum + (row.quantity * row.unit_price), 0);
    const totalDiscount = validRows.reduce((sum, row) => sum + row.discount, 0) + parseFloat(discount || 0);
    const totalTax = validRows.reduce((sum, row) => sum + row.tax_amount, 0) + parseFloat(orderTax || 0);
    const grandTotal = subtotal - totalDiscount + totalTax + parseFloat(shipping || 0);
    
    // Calculate wallet usage
    const walletBalance = selectedCustomer?.wallet_balance || 0;
    let walletToUse = 0;
    if (useWallet && selectedCustomer && walletBalance > 0 && paymentType === 'pay_now') {
      if (walletAmount > 0) {
        walletToUse = Math.min(walletAmount, walletBalance, grandTotal);
      } else {
        // Use all available wallet balance (up to grand total)
        walletToUse = Math.min(walletBalance, grandTotal);
      }
    }
    
    // Calculate payment amounts
    const amountPaidValue = parseFloat(amountPaid) || 0;
    const totalPayment = amountPaidValue + walletToUse;
    const change = paymentType === 'pay_now' ? Math.max(0, totalPayment - grandTotal) : 0;
    const balance = paymentType === 'pay_now' ? Math.max(0, grandTotal - totalPayment) : grandTotal;
    
    return {
      subtotal,
      totalDiscount,
      totalTax,
      shipping: parseFloat(shipping || 0),
      grandTotal,
      change,
      balance,
      walletBalance,
      walletToUse,
      totalPayment,
    };
  };

  const processSale = async (allowPartial = false, excessChoice = 'change') => {
    // Filter out empty rows
    const validRows = productRows.filter(row => row.product_id);
    
    if (validRows.length === 0) {
      toast.error('Please add at least one product by searching and selecting', 8000);
      return;
    }

    const totals = calculateTotals();
    
    // Format amount_paid to ensure it fits within max_digits=10, decimal_places=2 constraint
    // Max value: 99,999,999.99 (8 digits before decimal + 2 after = 10 total)
    const formatAmountPaid = (amount) => {
      // Round to 2 decimal places
      let formatted = Math.round(amount * 100) / 100;
      // Ensure it doesn't exceed max value
      const maxValue = 99999999.99;
      if (formatted > maxValue) {
        formatted = maxValue;
      }
      // Return as number (not string) to avoid precision issues
      return parseFloat(formatted.toFixed(2));
    };
    
    // Use confirmed amount from pendingSaleData if available (when called from confirmation dialog)
    // This ensures the amount sent matches what the user confirmed, even if state changed
    // pendingSaleData.paid includes wallet usage, so we need to extract just the cash amount
    const confirmedPaid = pendingSaleData?.paid;
    let amountPaidValue = 0;
    
    if (paymentType === 'pay_now') {
      if (confirmedPaid !== undefined) {
        // If confirmed, use the confirmed paid amount minus wallet usage
        // pendingSaleData.paid = cash + wallet, so we subtract wallet to get cash amount
        const walletUsed = pendingSaleData.walletToUse || 0;
        const cashAmount = confirmedPaid - walletUsed;
        amountPaidValue = formatAmountPaid(cashAmount);
      } else {
        // Not from confirmation, use current state
        amountPaidValue = formatAmountPaid(parseFloat(amountPaid) || 0);
      }
    }
    
    const saleData = {
      sale_type: 'normal',
      items: validRows.map(row => ({
        product_id: row.product_id,
        variant_id: row.variant_id,
        quantity: row.quantity,
        unit_price: row.unit_price,
      })),
      customer_id: selectedCustomer ? selectedCustomer.id : null,
      customer_name: selectedCustomer ? selectedCustomer.name : (paymentMethod === 'cash' ? 'Cash Customer' : ''),
      customer_email: selectedCustomer ? selectedCustomer.email : '',
      customer_phone: selectedCustomer ? selectedCustomer.phone : '',
      customer_address: selectedCustomer ? selectedCustomer.address : '',
      tax_amount: totals.totalTax,
      discount_amount: totals.totalDiscount,
      delivery_method: deliveryMethod,
      delivery_cost: parseFloat(shipping || 0),
      shipping_address: shippingAddress || null,
      shipping_location: shippingLocation || null,
      amount_paid: amountPaidValue,
      payment_method: paymentType === 'pay_now' ? paymentMethod : 'other',
      notes: notes,
      due_date: dueDate || null,
      create_payment_plan: paymentType === 'installments',
      use_wallet: paymentType === 'pay_now' && useWallet && selectedCustomer ? true : false,
      wallet_amount: paymentType === 'pay_now' && useWallet && selectedCustomer 
        ? (pendingSaleData?.walletToUse !== undefined ? pendingSaleData.walletToUse : (parseFloat(walletAmount) || 0))
        : 0,
      allow_partial_payment: allowPartial,
      excess_payment_choice: excessChoice, // 'change' or 'wallet'
      // Only include payment plan fields if creating a payment plan
      ...(paymentType === 'installments' ? {
        number_of_installments: paymentPlanData.number_of_installments,
        installment_frequency: paymentPlanData.frequency,
        payment_plan_start_date: paymentPlanData.start_date,
      } : {
        // Explicitly set to null for pay_now to avoid validation errors
        number_of_installments: null,
        installment_frequency: null,
        payment_plan_start_date: null,
      }),
    };

    try {
      const response = await onSave(saleData);
      
      // Show wallet credit message if overpayment was added to wallet
      if (response?.data?.wallet_credit_added) {
        toast.success(
          `Sale completed! ${formatCurrency(response.data.wallet_credit_added)} added to customer wallet.`,
          8000
        );
      } else if (response?.data?.wallet_amount_used > 0) {
        toast.success(
          `Sale completed! Used ${formatCurrency(response.data.wallet_amount_used)} from customer wallet.`,
          5000
        );
      } else if (allowPartial && pendingSaleData && pendingSaleData.balance > 0) {
        toast.success(
          `Sale completed! Unpaid balance of ${formatCurrency(pendingSaleData.balance)} added to ${selectedCustomer?.name || 'customer'}'s account as debt. They can pay this later.`,
          8000
        );
      } else if (pendingSaleData && pendingSaleData.excess > 0 && excessChoice === 'wallet') {
        toast.success(
          `Sale completed! Excess payment of ${formatCurrency(pendingSaleData.excess)} added to ${selectedCustomer?.name || 'customer'}'s wallet.`,
          8000
        );
      }
      
      setShowPartialPaymentConfirm(false);
      setShowExcessPaymentConfirm(false);
      setPendingSaleData(null);
      handleClose();
    } catch (error) {
      setShowPartialPaymentConfirm(false);
      setShowExcessPaymentConfirm(false);
      setPendingSaleData(null);
      // Improved error handling to show detailed validation errors
      let errorMessage = 'Failed to create sale';
      
      if (error.response?.data) {
        const errorData = error.response.data;
        
        // Handle field-level validation errors (DRF format)
        if (typeof errorData === 'object' && !errorData.error) {
          const fieldErrors = [];
          for (const [field, messages] of Object.entries(errorData)) {
            if (Array.isArray(messages)) {
              fieldErrors.push(`${field}: ${messages.join(', ')}`);
            } else {
              fieldErrors.push(`${field}: ${messages}`);
            }
          }
          errorMessage = fieldErrors.join('; ');
        } else if (errorData.error) {
          errorMessage = errorData.error;
        } else if (typeof errorData === 'string') {
          errorMessage = errorData;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage, 8000);
    }
  };

  const handleSubmit = async () => {
    // For installments, customer is recommended but not strictly required
    // For pay_now with cash, customer can be optional
    if (!selectedCustomer && paymentType === 'installments') {
      const proceed = window.confirm(
        'No customer selected. Installment payments typically require a customer. ' +
        'Do you want to proceed without a customer?'
      );
      if (!proceed) {
        return;
      }
    }

    // Filter out empty rows
    const validRows = productRows.filter(row => row.product_id);
    
    if (validRows.length === 0) {
      toast.error('Please add at least one product by searching and selecting', 8000);
      return;
    }

    const totals = calculateTotals();

    // Validate based on payment type
    if (paymentType === 'pay_now') {
      const paid = parseFloat(amountPaid) || 0;
      if (paid <= 0) {
        toast.error('Please enter the amount paid', 8000);
        return;
      }
      
      const totalPayment = paid + totals.walletToUse;
      
      // Check if partial payment (paid < grandTotal)
      if (totalPayment < totals.grandTotal) {
        // Customer must be selected for partial payment
        if (!selectedCustomer) {
          toast.error('Please select a customer to allow partial payment. The unpaid amount will be added to their account as debt.', 8000);
          return;
        }
        
        // Show confirmation dialog
        const balance = totals.grandTotal - totalPayment;
        setPendingSaleData({ 
          total: totals.grandTotal, 
          paid: totalPayment, 
          balance,
          walletToUse: totals.walletToUse
        });
        setShowPartialPaymentConfirm(true);
        return;
      }
      
      // Check if excess payment (paid > grandTotal)
      if (totalPayment > totals.grandTotal && selectedCustomer) {
        const excess = totalPayment - totals.grandTotal;
        setPendingSaleData({ 
          total: totals.grandTotal, 
          paid: totalPayment, 
          excess,
          walletToUse: totals.walletToUse
        });
        setExcessPaymentChoice('change'); // Default to change
        setShowExcessPaymentConfirm(true);
        return;
      }
    } else if (paymentType === 'installments') {
      if (!paymentPlanData.start_date) {
        toast.error('Please select a start date for the payment plan', 8000);
        return;
      }
      if (paymentPlanData.number_of_installments < 1) {
        toast.error('Number of installments must be at least 1', 8000);
        return;
      }
    }
    
    // Validate customer for pay_now if not cash
    if (!selectedCustomer && paymentType === 'pay_now' && paymentMethod !== 'cash') {
      toast.error('Please select a customer for non-cash payments', 8000);
      return;
    }
    
    // If we get here, proceed with normal sale (full payment or installments)
    await processSale(false);
  };


  const handleClose = () => {
    setProductRows([]);
    setSelectedCustomer(null);
    setCustomerSearch('');
    setShowCustomerSearch(false);
    setProductSearch('');
    setProductSearchResults([]);
    setShowProductSearch(false);
    setOrderTax(0);
    setDiscount(0);
    setShipping(0);
    setDeliveryMethod('pickup');
    setShippingAddress('');
    setShippingLocation('');
    setStatus('pending');
    setDueDate('');
    setNotes('');
    setPaymentType('pay_now');
    setPaymentMethod('cash');
    setAmountPaid(0);
    setAmountPaidManuallySet(false);
    setPaymentPlanData({
      number_of_installments: 1,
      frequency: 'monthly',
      start_date: '',
    });
    onClose();
  };

  const totals = calculateTotals();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center overflow-y-auto bg-black/60 p-4 max-md:p-0" onClick={handleClose}>
      <div className="flex max-h-[90vh] w-full max-w-6xl flex-col rounded-lg bg-background shadow-xl max-md:max-h-screen max-md:rounded-none" onClick={(e) => e.stopPropagation()}>
        <div className="flex shrink-0 items-center justify-between border-b px-6 py-4">
          <h2 className="text-xl font-semibold">Add Sales</h2>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-destructive text-destructive-foreground transition-colors hover:bg-destructive/90"
            onClick={handleClose}
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Top Row: Customer, Date, Supplier */}
          <div className="form-row mb-6">
            <div className="form-group">
              <label>Customer Name *</label>
              <div className="flex items-stretch gap-2">
                <div className="relative" style={{ flex: 1 }}>
                  <input
                    type="text"
                    placeholder={selectedCustomer ? `${selectedCustomer.name} (${selectedCustomer.customer_code || 'N/A'})` : "Search customer by name, code, phone, or email..."}
                    value={customerSearch}
                    onChange={(e) => {
                      const value = e.target.value;
                      setCustomerSearch(value);
                      // Clear selected customer if user starts typing
                      if (selectedCustomer && value !== selectedCustomer.name) {
                        setSelectedCustomer(null);
                      }
                    }}
                    onFocus={() => {
                      // Refresh customers when input is focused to get newly added customers
                      loadCustomers();
                      // Show dropdown when focused if there are customers or search text
                      if (filteredCustomers.length > 0 || customerSearch) {
                        setShowCustomerSearch(true);
                      } else if (customers.length > 0) {
                        // Show all customers if no search
                        setFilteredCustomers(customers);
                        setShowCustomerSearch(true);
                      }
                    }}
                    onBlur={() => {
                      // Delay hiding to allow click on dropdown
                      setTimeout(() => setShowCustomerSearch(false), 200);
                    }}
                    required
                  />
                  {showCustomerSearch && (
                    <div className="absolute left-0 right-0 top-full z-[100] mt-1 max-h-[300px] overflow-y-auto rounded-md border border-border bg-background shadow-md">
                      {filteredCustomers.length > 0 ? (
                        filteredCustomers.map(customer => (
                          <div
                            key={customer.id}
                            className="cursor-pointer border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-muted"
                            onMouseDown={(e) => {
                              // Use onMouseDown to prevent onBlur from firing first
                              e.preventDefault();
                              setSelectedCustomer(customer);
                              setCustomerSearch('');
                              setShowCustomerSearch(false);
                            }}
                            onClick={() => {
                              setSelectedCustomer(customer);
                              setCustomerSearch('');
                              setShowCustomerSearch(false);
                            }}
                          >
                            <div className="mb-1 font-medium text-foreground">{customer.name}</div>
                            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                              {customer.customer_code && <span>Code: {customer.customer_code}</span>}
                              {customer.phone && <span>Phone: {customer.phone}</span>}
                              {customer.email && <span>Email: {customer.email}</span>}
                            </div>
                          </div>
                        ))
                      ) : customerSearch ? (
                        <div className="cursor-pointer border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-muted">
                          <div className="mb-1 font-medium text-foreground">No customers found</div>
                          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                            <span>Try a different search term</span>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-lg text-primary-foreground hover:bg-primary/90"
                  onClick={() => setShowCustomerFormModal(true)}
                  title="Add New Customer"
                >
                  +
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>Date *</label>
              <input
                type="date"
                value={saleDate}
                onChange={(e) => setSaleDate(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                min={saleDate}
              />
            </div>
          </div>

          {/* Product Selection - Extended Search Bar */}
          <div className="form-row mb-6">
            <div className="form-group col-span-full">
              <label>Search & Add Products *</label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Type product name, SKU, or barcode to search and add..."
                  className="pr-10"
                  value={productSearch}
                  onChange={handleProductSearchChange}
                  onFocus={() => {
                    if (productSearchResults.length > 0) {
                      setShowProductSearch(true);
                    }
                  }}
                  onKeyDown={(e) => {
                    // Allow Enter key to select first result
                    if (e.key === 'Enter' && productSearchResults.length > 0) {
                      e.preventDefault();
                      handleProductSelect(productSearchResults[0]);
                    }
                    // Escape to close dropdown
                    if (e.key === 'Escape') {
                      setShowProductSearch(false);
                    }
                  }}
                  onBlur={() => {
                    // Delay hiding to allow click on dropdown
                    setTimeout(() => {
                      setShowProductSearch(false);
                    }, 200);
                  }}
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">📷</span>
                {showProductSearch && productSearchResults.length > 0 && (
                  <div className="absolute left-0 right-0 top-full z-[100] mt-1 max-h-[300px] overflow-y-auto rounded-md border border-border bg-background shadow-md">
                    {productSearchResults.map(product => (
                      <div
                        key={product.id}
                        className="cursor-pointer border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-muted"
                        onMouseDown={(e) => {
                          // Use onMouseDown to prevent onBlur from firing first
                          e.preventDefault();
                          handleProductSelect(product);
                        }}
                        onClick={() => handleProductSelect(product)}
                      >
                        <div className="mb-1 font-medium text-foreground">{product.name}</div>
                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                          {product.sku && <span>SKU: {product.sku}</span>}
                          <span style={{ fontWeight: '600', color: '#059669' }}>{formatCurrency(product.price)}</span>
                          {product.stock !== undefined && (
                            <span style={{ color: product.stock > 0 ? '#059669' : '#dc2626' }}>
                              Stock: {product.stock}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Product Table */}
          <div className="my-6 overflow-hidden rounded-md border border-border max-md:overflow-x-auto">
            <table className="w-full border-collapse bg-background max-md:min-w-[800px]">
              <thead className="bg-muted/40">
                <tr>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Product</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Qty</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Unit Price</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Discount</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Tax(%)</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Tax Amount</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Total</th>
                  <th className="whitespace-nowrap border-b-2 border-border px-3 py-2 text-left text-sm font-semibold">Action</th>
                </tr>
              </thead>
              <tbody>
                {productRows.map((row, index) => (
                  <tr key={index} className="border-b border-border last:border-b-0 hover:bg-muted/30">
                    <td className="px-3 py-2 align-middle">
                      {row.product_name ? (
                        <div className="min-w-[200px]">
                          <div className="mb-1 font-medium text-foreground">{row.product_name}</div>
                          {row.size && <span className="mr-2 mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">Size: {row.size}</span>}
                          {row.color && <span className="mr-2 mt-1 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">Color: {row.color}</span>}
                          {row.product_sku && (
                            <div className="mt-1 text-xs text-muted-foreground">SKU: {row.product_sku}</div>
                          )}
                        </div>
                      ) : (
                        <div className="relative">
                          <input
                            type="text"
                            placeholder="Search product..."
                            value={productSearch}
                            onChange={handleProductSearchChange}
                            onFocus={() => {
                              setSelectedProductRowIndex(index);
                              searchProducts(productSearch);
                            }}
                          />
                          {showProductSearch && productSearchResults.length > 0 && selectedProductRowIndex === index && (
                            <div className="absolute left-0 right-0 top-full z-[100] mt-1 max-h-[300px] overflow-y-auto rounded-md border border-border bg-background shadow-md">
                              {productSearchResults.map(product => (
                                <div
                                  key={product.id}
                                  className="cursor-pointer border-b border-border/50 px-3 py-2 last:border-b-0 hover:bg-muted"
                                  onMouseDown={(e) => {
                                    // Use onMouseDown to prevent onBlur from firing first
                                    e.preventDefault();
                                    handleProductSelect(product);
                                    setSelectedProductRowIndex(null);
                                  }}
                                  onClick={() => {
                                    handleProductSelect(product);
                                    setSelectedProductRowIndex(null);
                                  }}
                                >
                                  <div className="mb-1 font-medium text-foreground">{product.name}</div>
                                  <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                                    {product.sku && <span>SKU: {product.sku}</span>}
                                    <span style={{ fontWeight: '600', color: '#059669' }}>{formatCurrency(product.price)}</span>
                                    {product.stock !== undefined && (
                                      <span style={{ color: product.stock > 0 ? '#059669' : '#dc2626' }}>
                                        Stock: {product.stock}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 align-middle">
                      <input
                        type="number"
                        min="1"
                        value={row.quantity}
                        onChange={(e) => updateProductRow(index, 'quantity', e.target.value)}
                        disabled={!row.product_id}
                        className="w-full rounded border border-input px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2 align-middle">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.unit_price}
                        onChange={(e) => updateProductRow(index, 'unit_price', e.target.value)}
                        disabled={!row.product_id}
                        className="w-full rounded border border-input px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2 align-middle">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.discount}
                        onChange={(e) => updateProductRow(index, 'discount', e.target.value)}
                        disabled={!row.product_id}
                        className="w-full rounded border border-input px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2 align-middle">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.tax_percent}
                        onChange={(e) => updateProductRow(index, 'tax_percent', e.target.value)}
                        disabled={!row.product_id}
                        className="w-full rounded border border-input px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2 align-middle">{formatCurrency(row.tax_amount)}</td>
                    <td className="px-3 py-2 align-middle">{formatCurrency(row.total_cost)}</td>
                    <td className="px-3 py-2 text-center align-middle">
                      <button
                        type="button"
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-destructive text-destructive-foreground transition hover:bg-destructive/90 disabled:cursor-not-allowed disabled:opacity-30"
                        onClick={() => removeProductRow(index)}
                        title={row.product_id ? "Click to remove this product" : "No product to remove"}
                        disabled={!row.product_id}
                      >
                        {row.product_id ? '🗑️' : '○'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {productRows.length === 0 && (
              <div className="mt-2 rounded-md border-2 border-dashed border-border py-8 text-center italic text-muted-foreground">
                🔍 Search for products above to add them to the sale
                <br />
                <small className="mt-2 block text-xs">
                  Type product name, SKU, or barcode and click to add
                </small>
              </div>
            )}
          </div>

          {/* Bottom Row: Order Tax, Discount, Shipping, Status */}
          <div className="form-row mb-6">
            <div className="form-group">
              <label>Order Tax</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={orderTax}
                onChange={(e) => setOrderTax(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="form-group">
              <label>Discount</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={discount}
                onChange={(e) => setDiscount(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="form-group">
              <label>Delivery Method</label>
              <SearchableSelect
                value={deliveryMethod}
                onChange={(e) => {
                  setDeliveryMethod(e.target.value);
                  if (e.target.value === 'pickup') {
                    setShipping(0);
                  }
                }}
                options={[
                  { id: 'pickup', name: 'Pickup (No Charge)' },
                  { id: 'delivery', name: 'Standard Delivery' },
                  { id: 'express', name: 'Express Delivery' }
                ]}
                placeholder="Select Delivery Method"
              />
            </div>

            <div className="form-group">
              <label>Shipping Cost</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={shipping}
                onChange={(e) => setShipping(parseFloat(e.target.value) || 0)}
                disabled={deliveryMethod === 'pickup'}
              />
            </div>

            <div className="form-group">
              <label>Status</label>
              <SearchableSelect
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                options={[
                  { id: 'pending', name: 'Pending' },
                  { id: 'completed', name: 'Completed' },
                  { id: 'cancelled', name: 'Cancelled' }
                ]}
                placeholder="Select Status"
              />
            </div>
          </div>

          {/* Shipping Information Section */}
          {(deliveryMethod === 'delivery' || deliveryMethod === 'express') && (
            <div className="form-row mb-6">
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>Shipping Address</label>
                <textarea
                  rows="3"
                  value={shippingAddress}
                  onChange={(e) => setShippingAddress(e.target.value)}
                  placeholder="Enter full shipping address"
                />
              </div>
              <div className="form-group">
                <label>Location</label>
                <input
                  type="text"
                  value={shippingLocation}
                  onChange={(e) => setShippingLocation(e.target.value)}
                  placeholder="Enter location/area"
                />
              </div>
            </div>
          )}

          {/* Payment Type Section */}
          <div className="my-6">
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label>Payment Type *</label>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                <label className="flex cursor-pointer items-center gap-2 rounded-md border-2 border-border bg-background px-6 py-3 font-medium transition hover:border-primary/50 has-[:checked]:border-primary has-[:checked]:bg-primary/5">
                  <input
                    type="radio"
                    name="paymentType"
                    value="pay_now"
                    checked={paymentType === 'pay_now'}
                    onChange={(e) => {
                      setPaymentType(e.target.value);
                      setAmountPaidManuallySet(false);
                      // Auto-set amount paid to grand total when switching to pay now
                      if (e.target.value === 'pay_now') {
                        const totals = calculateTotals();
                        setAmountPaid(totals.grandTotal);
                      }
                    }}
                  />
                  <span>💳 Pay Now</span>
                </label>
                <label className="flex cursor-pointer items-center gap-2 rounded-md border-2 border-border bg-background px-6 py-3 font-medium transition hover:border-primary/50 has-[:checked]:border-primary has-[:checked]:bg-primary/5">
                  <input
                    type="radio"
                    name="paymentType"
                    value="installments"
                    checked={paymentType === 'installments'}
                    onChange={(e) => setPaymentType(e.target.value)}
                  />
                  <span>📅 Installments</span>
                </label>
              </div>
            </div>

            {/* Pay Now Fields */}
            {paymentType === 'pay_now' && (
              <div className="grid grid-cols-1 gap-4 rounded-md bg-primary/5 p-4 md:grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">
                {/* Wallet Balance Display */}
                {selectedCustomer && totals.walletBalance > 0 && (
                  <div className="form-group" style={{ gridColumn: '1 / -1', padding: '0.75rem', background: '#dbeafe', borderRadius: '6px', border: '1px solid #93c5fd' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <label style={{ margin: 0, fontWeight: '600', color: '#1e40af' }}>
                        💰 Customer Wallet Balance
                      </label>
                      <span style={{ fontWeight: '700', fontSize: '1.1rem', color: '#059669' }}>
                        {formatCurrency(totals.walletBalance)}
                      </span>
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={useWallet}
                        onChange={(e) => {
                          setUseWallet(e.target.checked);
                          if (!e.target.checked) {
                            setWalletAmount(0);
                          }
                        }}
                      />
                      <span style={{ fontWeight: '500' }}>Use wallet balance for payment</span>
                    </label>
                    {useWallet && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <input
                          type="number"
                          min="0"
                          max={totals.walletBalance}
                          step="0.01"
                          value={walletAmount}
                          onChange={(e) => setWalletAmount(parseFloat(e.target.value) || 0)}
                          placeholder={`Use all (${formatCurrency(totals.walletBalance)})`}
                          style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #93c5fd' }}
                        />
                        <small style={{ color: '#6b7280', display: 'block', marginTop: '0.25rem' }}>
                          {walletAmount === 0 || !walletAmount
                            ? `Will use all available: ${formatCurrency(totals.walletBalance)}`
                            : `Will use: ${formatCurrency(Math.min(walletAmount, totals.walletBalance, totals.grandTotal))}`
                          }
                        </small>
                      </div>
                    )}
                  </div>
                )}

                <div className="form-group">
                  <label>Payment Method *</label>
                  <SearchableSelect
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    options={[
                      { id: 'cash', name: 'Cash' },
                      { id: 'mpesa', name: 'M-PESA' },
                      { id: 'other', name: 'Other' }
                    ]}
                    placeholder="Select Payment Method"
                  />
                </div>

                <div className="form-group">
                  <label>Amount Paid *</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={amountPaid}
                    onChange={(e) => {
                      setAmountPaid(parseFloat(e.target.value) || 0);
                      setAmountPaidManuallySet(true);
                    }}
                    onFocus={() => setAmountPaidManuallySet(true)}
                    required
                    style={{ fontWeight: '600', fontSize: '1.1rem' }}
                  />
                  <small style={{ color: '#6b7280', marginTop: '0.25rem', display: 'block' }}>
                    Grand Total: {formatCurrency(totals.grandTotal)}
                    {totals.walletToUse > 0 && (
                      <span style={{ color: '#059669', display: 'block', marginTop: '0.25rem', fontWeight: '600' }}>
                        💰 Wallet: -{formatCurrency(totals.walletToUse)}
                      </span>
                    )}
                    {totals.totalPayment > totals.grandTotal && (
                      <span style={{ color: '#059669', display: 'block', marginTop: '0.25rem', fontWeight: '600' }}>
                        💰 Overpayment: {formatCurrency(totals.change)} will be added to wallet
                      </span>
                    )}
                    {totals.totalPayment > 0 && totals.totalPayment < totals.grandTotal && (
                      <span style={{ color: '#f59e0b', display: 'block', marginTop: '0.25rem' }}>
                        Balance: {formatCurrency(totals.balance)}
                      </span>
                    )}
                    {totals.totalPayment === totals.grandTotal && totals.totalPayment > 0 && (
                      <span style={{ color: '#059669', display: 'block', marginTop: '0.25rem' }}>
                        ✓ Fully paid
                      </span>
                    )}
                  </small>
                </div>
              </div>
            )}

            {/* Installments Fields */}
            {paymentType === 'installments' && (
              <div className="grid grid-cols-1 gap-4 rounded-md bg-warning/10 p-4 md:grid-cols-[repeat(auto-fit,minmax(200px,1fr))]">
                <div className="form-group">
                  <label>Number of Installments *</label>
                  <input
                    type="number"
                    min="1"
                    value={paymentPlanData.number_of_installments}
                    onChange={(e) => {
                      const installments = parseInt(e.target.value) || 1;
                      setPaymentPlanData({
                        ...paymentPlanData,
                        number_of_installments: installments
                      });
                    }}
                    required
                  />
                  <small style={{ color: '#6b7280', marginTop: '0.25rem', display: 'block' }}>
                    Total: {formatCurrency(totals.grandTotal)}
                    {paymentPlanData.number_of_installments > 0 && (
                      <span style={{ display: 'block', marginTop: '0.25rem', fontWeight: '600', color: '#059669' }}>
                        Per installment: {formatCurrency(totals.grandTotal / paymentPlanData.number_of_installments)}
                      </span>
                    )}
                  </small>
                </div>

                <div className="form-group">
                  <label>Frequency *</label>
                  <SearchableSelect
                    value={paymentPlanData.frequency}
                    onChange={(e) => setPaymentPlanData({
                      ...paymentPlanData,
                      frequency: e.target.value
                    })}
                    options={[
                      { id: 'daily', name: 'Daily' },
                      { id: 'weekly', name: 'Weekly' },
                      { id: 'biweekly', name: 'Bi-Weekly' },
                      { id: 'monthly', name: 'Monthly' },
                      { id: 'quarterly', name: 'Quarterly' }
                    ]}
                    placeholder="Select Frequency"
                  />
                </div>

                <div className="form-group">
                  <label>Start Date *</label>
                  <input
                    type="date"
                    value={paymentPlanData.start_date}
                    onChange={(e) => setPaymentPlanData({
                      ...paymentPlanData,
                      start_date: e.target.value
                    })}
                    min={saleDate}
                    required
                  />
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="form-group">
            <label>Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows="3"
              placeholder="Additional notes..."
            />
          </div>

          {/* Summary Box */}
          <div className="ml-auto mt-6 w-full max-w-xs rounded-md border border-border bg-muted/40 p-4 max-md:ml-0 max-md:max-w-full">
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span>Order Tax:</span>
              <span>{formatCurrency(totals.totalTax)}</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span>Discount:</span>
              <span>{formatCurrency(totals.totalDiscount)}</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-sm">
              <span>Shipping:</span>
              <span>{formatCurrency(totals.shipping)}</span>
            </div>
            <div className="flex justify-between border-b border-border py-2 text-base font-semibold mt-2 border-t-2 pt-3">
              <span>Grand Total:</span>
              <span>{formatCurrency(totals.grandTotal)}</span>
            </div>
          </div>
        </div>

        <div className="flex shrink-0 justify-end gap-4 border-t px-6 py-4 max-md:flex-col-reverse">
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSubmit} className="bg-orange-500 hover:bg-orange-600">
            Submit
          </Button>
        </div>
      </div>

      {/* Variant Selector Modal */}
      {showVariantSelector && selectedProduct && (
        <VariantSelector
          product={selectedProduct}
          onSelect={(productWithVariant) => {
            if (selectedProductRowIndex !== null && selectedProduct) {
              // Ensure row exists
              if (selectedProductRowIndex >= productRows.length) {
                addProductRow();
              }
              addProductToRow(selectedProduct, selectedProductRowIndex, productWithVariant.variant);
            }
            setShowProductSearch(false);
            setProductSearch('');
            setShowVariantSelector(false);
            setSelectedProduct(null);
            setSelectedProductRowIndex(null);
          }}
          onClose={() => {
            setShowVariantSelector(false);
            setSelectedProduct(null);
            setSelectedProductRowIndex(null);
          }}
        />
      )}

      {/* Partial Payment Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showPartialPaymentConfirm}
        title="Allow Customer to Pay Later?"
        message={
          pendingSaleData && selectedCustomer
            ? `Total: ${formatCurrency(pendingSaleData.total)}\nAmount Paid: ${formatCurrency(pendingSaleData.paid)}${pendingSaleData.walletToUse > 0 ? ` (including ${formatCurrency(pendingSaleData.walletToUse)} from wallet)` : ''}\nUnpaid Balance: ${formatCurrency(pendingSaleData.balance)}\n\nDo you want to proceed with this transaction? The unpaid balance of ${formatCurrency(pendingSaleData.balance)} will be added to ${selectedCustomer.name}'s account as debt. They can pay this amount later in installments.`
            : pendingSaleData
            ? `Total: ${formatCurrency(pendingSaleData.total)}\nAmount Paid: ${formatCurrency(pendingSaleData.paid)}\nUnpaid Balance: ${formatCurrency(pendingSaleData.balance)}\n\nDo you want to proceed with this transaction? The unpaid balance will be added to the customer's account as debt.`
            : ''
        }
        onConfirm={() => {
          // Proceed with the sale with partial payment allowed
          processSale(true);
        }}
        onCancel={() => {
          setShowPartialPaymentConfirm(false);
          setPendingSaleData(null);
        }}
        confirmText="Yes, Proceed"
        cancelText="Cancel"
        type="primary"
      />
      
      {/* Excess Payment Confirmation Dialog */}
      {showExcessPaymentConfirm && pendingSaleData && (
        <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/50 p-4" onClick={() => setShowExcessPaymentConfirm(false)}>
          <div className="w-full max-w-lg rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">Excess Payment</h2>
              <button
                type="button"
                onClick={() => setShowExcessPaymentConfirm(false)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="space-y-4 px-6 py-4">
              <p>
                <strong>Total:</strong> {formatCurrency(pendingSaleData.total)}<br />
                <strong>Paid:</strong> {formatCurrency(pendingSaleData.paid)}{pendingSaleData.walletToUse > 0 ? ` (including ${formatCurrency(pendingSaleData.walletToUse)} from wallet)` : ''}<br />
                <strong>Excess:</strong> {formatCurrency(pendingSaleData.excess)}
              </p>
              <p className="text-muted-foreground">How would you like to handle the excess payment?</p>
              <div className="flex flex-col gap-3">
                <label className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-md border p-3',
                  excessPaymentChoice === 'change' ? 'border-primary bg-primary/5' : 'border-border bg-background'
                )}>
                  <input
                    type="radio"
                    name="excessPayment"
                    value="change"
                    checked={excessPaymentChoice === 'change'}
                    onChange={(e) => setExcessPaymentChoice(e.target.value)}
                    className="mt-1"
                  />
                  <div>
                    <strong>Give Change</strong>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Return {formatCurrency(pendingSaleData.excess)} to the customer
                    </div>
                  </div>
                </label>
                <label className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-md border p-3',
                  excessPaymentChoice === 'wallet' ? 'border-primary bg-primary/5' : 'border-border bg-background'
                )}>
                  <input
                    type="radio"
                    name="excessPayment"
                    value="wallet"
                    checked={excessPaymentChoice === 'wallet'}
                    onChange={(e) => setExcessPaymentChoice(e.target.value)}
                    className="mt-1"
                  />
                  <div>
                    <strong>Add to Wallet</strong>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Add {formatCurrency(pendingSaleData.excess)} to {selectedCustomer?.name || 'customer'}&apos;s wallet for future use
                    </div>
                  </div>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t px-6 py-4">
              <Button type="button" variant="outline" onClick={() => setShowExcessPaymentConfirm(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  processSale(false, excessPaymentChoice);
                }}
              >
                Complete Sale
              </Button>
            </div>
          </div>
        </div>
      )}
      
      {/* Customer Form Modal */}
      <CustomerFormModal
        isOpen={showCustomerFormModal}
        onClose={() => setShowCustomerFormModal(false)}
        onCustomerCreated={(newCustomer) => {
          // Reload customers list
          loadCustomers();
          // Auto-select the newly created customer
          setSelectedCustomer(newCustomer);
          setCustomerSearch(newCustomer.name);
          setShowCustomerFormModal(false);
        }}
      />
    </div>
  );
};

export default NormalSaleModal;
