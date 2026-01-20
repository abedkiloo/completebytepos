import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { productsAPI, categoriesAPI, salesAPI, customersAPI, authAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Receipt from './Receipt';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import VariantSelector from './VariantSelector';
import BranchSelector from '../BranchSelector/BranchSelector';
import { toast } from '../../utils/toast';
import './POS.css';

const POS = () => {
  // POS doesn't need Layout wrapper as it has its own full-screen layout
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [cart, setCart] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [expandedCategories, setExpandedCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [user, setUser] = useState(null);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [orderNumber, setOrderNumber] = useState(`#ORD${Date.now().toString().slice(-6)}`);
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [receivedAmount, setReceivedAmount] = useState('');
  const [shipping, setShipping] = useState(0);
  const [tax, setTax] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [discountType, setDiscountType] = useState('percentage'); // 'flat' or 'percentage'
  const [coupon] = useState(0); // Reserved for future coupon functionality
  const [roundoff] = useState(false); // Reserved for future roundoff functionality
  const [featuredFilter, setFeaturedFilter] = useState(false);
  const [deliveryMethod, setDeliveryMethod] = useState('pickup'); // 'pickup', 'delivery', 'express'
  const [deliveryCost, setDeliveryCost] = useState(0);
  const [shippingAddress, setShippingAddress] = useState('');
  const [shippingLocation, setShippingLocation] = useState('');
  const [hasExtraPayment, setHasExtraPayment] = useState(false);
  const [extraPaymentAmount, setExtraPaymentAmount] = useState(0);
  const [showShippingModal, setShowShippingModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [showReceipt, setShowReceipt] = useState(false);
  const [lastSale, setLastSale] = useState(null);
  const [showConfirmClear, setShowConfirmClear] = useState(false);
  const [showVariantSelector, setShowVariantSelector] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  useEffect(() => {
    loadCategories();
    loadProducts();
    loadCustomers();
    loadUser();
    
    // Update time every second
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    
    return () => clearInterval(timeInterval);
  }, []);

  useEffect(() => {
    if (searchQuery) {
      searchProducts();
    } else {
      loadProducts();
    }
  }, [searchQuery, selectedCategory, selectedSubcategory, featuredFilter]);

  const loadUser = async () => {
    try {
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      } else {
        const response = await authAPI.me();
        setUser(response.data?.user || response.data);
      }
    } catch (error) {
      console.error('Error loading user:', error);
      setUser({ username: 'Admin' });
    }
  };

  const loadCustomers = async () => {
    try {
      const response = await customersAPI.list({ is_active: true });
      const customersData = response.data.results || response.data || [];
      setCustomers(Array.isArray(customersData) ? customersData : []);
    } catch (error) {
      console.error('Error loading customers:', error);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await categoriesAPI.list({ is_active: 'true' });
      const categoriesData = response.data.results || response.data || [];
      // Organize categories with their children (subcategories)
      const organizedCategories = categoriesData.map(cat => {
        const children = categoriesData.filter(c => c.parent === cat.id);
        return { ...cat, children };
      }).filter(cat => !cat.parent); // Only show top-level categories
      setCategories(organizedCategories);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  };

  const toggleCategory = (categoryId) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryId]: !prev[categoryId]
    }));
  };

  const handleCategorySelect = (categoryId, subcategoryId = null) => {
    setSelectedCategory(categoryId);
    setSelectedSubcategory(subcategoryId);
  };

  const loadProducts = async () => {
    setLoading(true);
    try {
      const params = { is_active: 'true' };
      if (selectedCategory !== 'all') {
        params.category = selectedCategory;
      }
      if (selectedSubcategory) {
        params.subcategory = selectedSubcategory;
      }
      if (searchQuery) {
        params.search = searchQuery;
      }
      if (featuredFilter) {
        // Assuming featured products have a featured flag or similar
        // For now, we'll just filter by search
      }

      const response = await productsAPI.list(params);
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
    } finally {
      setLoading(false);
    }
  };

  const searchProducts = useCallback(async () => {
    if (!searchQuery.trim()) {
      loadProducts();
      return;
    }

    setLoading(true);
    try {
      const response = await productsAPI.search(searchQuery, 50);
      setProducts(response.data || []);
    } catch (error) {
      console.error('Error searching products:', error);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  const addToCart = (product) => {
    // If product has variants, show variant selector
    // Check both available_sizes_detail/available_colors_detail (from API) and available_sizes/available_colors (fallback)
    const hasSizes = (product.available_sizes_detail && product.available_sizes_detail.length > 0) || 
                     (product.available_sizes && product.available_sizes.length > 0);
    const hasColors = (product.available_colors_detail && product.available_colors_detail.length > 0) || 
                      (product.available_colors && product.available_colors.length > 0);
    
    if (product.has_variants && (hasSizes || hasColors)) {
      setSelectedProduct(product);
      setShowVariantSelector(true);
      return;
    }
    
    // Otherwise, add directly to cart
    addProductToCart(product);
  };

  const addProductToCart = (product) => {
    // Create unique key for cart items (product + variant)
    const cartKey = product.variant_id 
      ? `${product.id}-${product.variant_id}` 
      : `${product.id}`;
    
    const existingItem = cart.find(item => {
      const itemKey = item.variant_id 
        ? `${item.id}-${item.variant_id}` 
        : `${item.id}`;
      return itemKey === cartKey;
    });
    
    // Get quantity from product (if set by variant selector) or default to 1
    const quantityToAdd = product.quantity || 1;
    
    if (existingItem) {
      setCart(cart.map(item => {
        const itemKey = item.variant_id 
          ? `${item.id}-${item.variant_id}` 
          : `${item.id}`;
        if (itemKey === cartKey) {
          return { ...item, quantity: item.quantity + quantityToAdd };
        }
        return item;
      }));
    } else {
      setCart([...cart, {
        ...product,
        quantity: quantityToAdd,
        price: parseFloat(product.price),
        sku: product.sku || product.variant?.sku || '',
        stock_quantity: product.stock_quantity !== undefined 
          ? product.stock_quantity 
          : (product.variant?.stock_quantity || 0),
      }]);
    }
    
    setShowVariantSelector(false);
    setSelectedProduct(null);
  };

  const updateQuantity = (cartItem, change) => {
    setCart(cart.map(item => {
      const itemKey = item.variant_id 
        ? `${item.id}-${item.variant_id}` 
        : `${item.id}`;
      const cartKey = cartItem.variant_id 
        ? `${cartItem.id}-${cartItem.variant_id}` 
        : `${cartItem.id}`;
      
      if (itemKey === cartKey) {
        const newQuantity = Math.max(0, item.quantity + change);
        if (newQuantity === 0) {
          return null;
        }
        return { ...item, quantity: newQuantity };
      }
      return item;
    }).filter(Boolean));
  };

  const setQuantityDirectly = (cartItem, newQuantity) => {
    const quantity = Math.max(0, parseInt(newQuantity) || 0);
    if (quantity === 0) {
      removeFromCart(cartItem);
      return;
    }
    setCart(cart.map(item => {
      const itemKey = item.variant_id 
        ? `${item.id}-${item.variant_id}` 
        : `${item.id}`;
      const cartKey = cartItem.variant_id 
        ? `${cartItem.id}-${cartItem.variant_id}` 
        : `${cartItem.id}`;
      
      if (itemKey === cartKey) {
        return { ...item, quantity: quantity };
      }
      return item;
    }));
  };

  const removeFromCart = (cartItem) => {
    setCart(cart.filter(item => {
      const itemKey = item.variant_id 
        ? `${item.id}-${item.variant_id}` 
        : `${item.id}`;
      const cartKey = cartItem.variant_id 
        ? `${cartItem.id}-${cartItem.variant_id}` 
        : `${cartItem.id}`;
      return itemKey !== cartKey;
    }));
  };

  const clearCart = () => {
    setShowConfirmClear(true);
  };

  const confirmClearCart = () => {
    setCart([]);
    setShowConfirmClear(false);
    toast.info('Cart cleared');
  };

  const calculateSubtotal = () => {
    return cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  };

  const calculateDiscountAmount = () => {
    const subtotal = calculateSubtotal();
    if (discountType === 'percentage') {
      return (subtotal * discount) / 100;
    }
    return discount;
  };

  const calculateTaxAmount = () => {
    const subtotal = calculateSubtotal();
    const discountAmount = calculateDiscountAmount();
    return (subtotal - discountAmount - coupon) * (tax / 100);
  };

  const calculateRoundoff = () => {
    if (!roundoff) return 0;
    const subtotal = calculateSubtotal();
    const discountAmount = calculateDiscountAmount();
    const taxAmount = calculateTaxAmount();
    const totalBeforeRoundoff = subtotal - discountAmount - coupon + taxAmount + shipping + deliveryCost;
    const rounded = Math.round(totalBeforeRoundoff);
    return rounded - totalBeforeRoundoff;
  };

  const calculateTotal = () => {
    const subtotal = calculateSubtotal();
    const discountAmount = calculateDiscountAmount();
    const taxAmount = calculateTaxAmount();
    const roundoffAmount = calculateRoundoff();
    const extraPayment = hasExtraPayment ? parseFloat(extraPaymentAmount) || 0 : 0;
    return subtotal - discountAmount - coupon + taxAmount + shipping + deliveryCost + extraPayment + roundoffAmount;
  };

  const handlePayment = async () => {
    if (cart.length === 0) {
      toast.warning('Cart is empty');
      return;
    }

    const total = calculateTotal();
    const received = parseFloat(receivedAmount) || 0;
    
    // Validate payment for cash/mpesa
    if (paymentMethod === 'cash' || paymentMethod === 'mpesa') {
      if (!receivedAmount || received <= 0) {
        toast.warning('Please enter received amount');
        return;
      }
      if (received < total) {
        toast.warning('Received amount is less than total');
        return;
      }
    }

    try {
      const subtotal = calculateSubtotal();
      const discountAmount = calculateDiscountAmount();
      const taxAmount = (subtotal - discountAmount) * (tax / 100);
      const extraPayment = hasExtraPayment ? parseFloat(extraPaymentAmount) || 0 : 0;
      const finalTotal = subtotal - discountAmount + taxAmount + shipping + deliveryCost + extraPayment;
      
      const saleData = {
        items: cart.map(item => ({
          product_id: item.id,
          variant_id: item.variant_id || null,
          quantity: item.quantity,
          unit_price: parseFloat(item.price),
        })),
        tax_amount: parseFloat(taxAmount.toFixed(2)),
        discount_amount: parseFloat(discountAmount.toFixed(2)),
        delivery_method: deliveryMethod,
        delivery_cost: parseFloat(deliveryCost.toFixed(2)),
        shipping_address: shippingAddress || null,
        shipping_location: shippingLocation || null,
        payment_method: paymentMethod,
        amount_paid: (paymentMethod === 'cash' || paymentMethod === 'mpesa') ? parseFloat(received.toFixed(2)) : parseFloat(finalTotal.toFixed(2)),
        notes: hasExtraPayment ? `Extra Payment: ${formatCurrency(extraPayment)}` : '',
        customer_id: selectedCustomer?.id || null,
        sale_type: 'pos',
      };
      
      // Generate new order number for next order
      setOrderNumber(`#ORD${Date.now().toString().slice(-6)}`);

      const response = await salesAPI.create(saleData);
      // Add change to the sale data for receipt display
      const saleWithChange = {
        ...response.data,
        change: (paymentMethod === 'cash' || paymentMethod === 'mpesa') 
          ? Math.max(0, received - total) 
          : 0
      };
      setLastSale(saleWithChange);
      setCart([]);
      setShowPaymentModal(false);
      setShowShippingModal(false);
      setShowSuccessModal(true);
      setReceivedAmount('');
      setShipping(0);
      setTax(0);
      setShippingAddress('');
      setShippingLocation('');
      setHasExtraPayment(false);
      setExtraPaymentAmount(0);
      setDeliveryCost(0);
      setDeliveryMethod('pickup');
      setDiscount(0);
      setDeliveryMethod('pickup');
      setDeliveryCost(0);
      toast.success('Sale completed successfully');
    } catch (error) {
      toast.error('Failed to complete sale: ' + (error.response?.data?.error || error.message));
    }
  };

  const getCartItemCount = () => {
    return cart.reduce((sum, item) => sum + item.quantity, 0);
  };

  // Reserved for future use
  // const isProductInCart = (productId, variantId = null) => {
  //   return cart.some(item => {
  //     if (item.id !== productId) return false;
  //     if (variantId !== null) {
  //       return item.variant_id === variantId;
  //     }
  //     return !item.variant_id;
  //   });
  // };

  // const getProductQuantity = (productId, variantId = null) => {
  //   const item = cart.find(item => {
  //     if (item.id !== productId) return false;
  //     if (variantId !== null) {
  //       return item.variant_id === variantId;
  //     }
  //     return !item.variant_id;
  //   });
  //   return item ? item.quantity : 0;
  // };

  // Reserved for future payment methods selection
  // const paymentMethods = [
  //   { id: 'cash', label: 'Cash', icon: '💵', color: '#10b981' },
  //   { id: 'deposit', label: 'Deposit', icon: '📦', color: '#f97316' },
  //   { id: 'pay_later', label: 'Pay Later', icon: '📅', color: '#f97316' },
  //   { id: 'external', label: 'External', icon: '🔗', color: '#a855f7' },
  //   { id: 'mpesa', label: 'Mobile Money', icon: '📱', color: '#10b981' },
  // ];

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  };

  const change = (paymentMethod === 'cash' || paymentMethod === 'mpesa') && receivedAmount 
    ? Math.max(0, parseFloat(receivedAmount) - calculateTotal())
    : 0;

  // Topbar icon handlers
  const handleCalculator = () => {
    // Open system calculator or show a simple calculator modal
    window.open('calculator:', '_blank');
  };

  const handleExpand = () => {
    // Toggle fullscreen
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        toast.error('Unable to enter fullscreen mode');
      });
    } else {
      document.exitFullscreen();
    }
  };

  const handlePrint = () => {
    // Print current receipt if available
    if (lastSale && showReceipt) {
      window.print();
    } else {
      toast.info('No receipt available to print');
    }
  };

  const handleRefresh = () => {
    loadProducts();
    loadCategories();
    toast.success('Products refreshed');
  };

  const handleChart = () => {
    navigate('/reports');
  };

  const handleSettings = () => {
    navigate('/module-settings');
  };

  return (
    <div className="pos-container">
      {/* Top Bar */}
      <div className="pos-topbar">
        <div className="topbar-left">
          <div className="logo">
            <img src="/logo.svg" alt="CompleteByte POS" className="logo-img" />
          </div>
          <div className="time-display">{formatTime(currentTime)}</div>
        </div>
        <div className="topbar-center">
          <div className="topbar-nav">
            <a href="/" className="nav-link">Dashboard</a>
            <BranchSelector />
          </div>
        </div>
        <div className="topbar-right">
          <div className="topbar-icon" title="Calculator" onClick={handleCalculator}>🔢</div>
          <div className="topbar-icon" title="Toggle Fullscreen" onClick={handleExpand}>⛶</div>
          <div className="topbar-icon" title="Print Receipt" onClick={handlePrint}>🖨️</div>
          <div className="topbar-icon" title="Refresh Products" onClick={handleRefresh}>🔄</div>
          <div className="topbar-icon" title="Reports" onClick={handleChart}>📊</div>
          <div className="topbar-icon" title="Settings" onClick={handleSettings}>⚙️</div>
          <div className="user-profile">
            <div className="user-avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</div>
            <span>{user?.username || 'Admin'}</span>
          </div>
        </div>
      </div>

      <div className="pos-content">
        {/* Left Sidebar - Categories */}
        <div className="pos-sidebar-left">
          <div className="category-list">
            <div
              className={`category-item ${selectedCategory === 'all' ? 'active' : ''}`}
              onClick={() => handleCategorySelect('all')}
            >
              <span className="category-icon">📦</span>
              <span>All</span>
            </div>
            {categories.map(category => {
              const hasChildren = category.children && category.children.length > 0;
              const isExpanded = expandedCategories[category.id];
              const isActive = selectedCategory === category.id && !selectedSubcategory;
              
              return (
                <div key={category.id} className="category-group">
                  <div
                    className={`category-item ${isActive ? 'active' : ''} ${hasChildren ? 'has-children' : ''}`}
                    onClick={() => {
                      if (hasChildren) {
                        toggleCategory(category.id);
                      }
                      handleCategorySelect(category.id);
                    }}
                  >
                    <span className="category-icon">📁</span>
                    <span>{category.name}</span>
                    {hasChildren && (
                      <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                    )}
                  </div>
                  {hasChildren && isExpanded && (
                    <div className="subcategory-list">
                      <div
                        className={`subcategory-item ${selectedCategory === category.id && !selectedSubcategory ? 'active' : ''}`}
                        onClick={() => handleCategorySelect(category.id)}
                      >
                        <span className="subcategory-icon">→</span>
                        <span>All {category.name}</span>
                      </div>
                      {category.children.map(subcategory => (
                        <div
                          key={subcategory.id}
                          className={`subcategory-item ${selectedSubcategory === subcategory.id ? 'active' : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCategorySelect(category.id, subcategory.id);
                          }}
                        >
                          <span className="subcategory-icon">→</span>
                          <span>{subcategory.name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Center - Products Grid */}
        <div className="pos-main">
          <div className="products-header">
            <div className="products-search-filter">
              <div className="search-box-main">
                <input
                  type="text"
                  placeholder="Q Search Product"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <span className="search-icon-main">🔍</span>
              </div>
              <div className="filter-buttons">
                <button 
                  className={`filter-btn ${!featuredFilter ? 'active' : ''}`}
                  onClick={() => setFeaturedFilter(false)}
                >
                  View All Brands
                </button>
                <button 
                  className={`filter-btn ${featuredFilter ? 'active' : ''}`}
                  onClick={() => setFeaturedFilter(true)}
                >
                  Featured
                </button>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="loading-products">Loading products...</div>
          ) : (
            <div className="products-grid">
              {products.length === 0 ? (
                <div className="no-products">No products found</div>
              ) : (
                products.map(product => {
                  // Check if product has variants enabled
                  const hasSizes = (product.available_sizes_detail && product.available_sizes_detail.length > 0) || 
                                   (product.available_sizes && product.available_sizes.length > 0);
                  const hasColors = (product.available_colors_detail && product.available_colors_detail.length > 0) || 
                                    (product.available_colors && product.available_colors.length > 0);
                  const hasVariants = product.has_variants && (hasSizes || hasColors);
                  
                  // For products with variants, we can't use simple base-product-only checks
                  // Instead, check if ANY variant or base product with this id is in cart
                  const productVariantsInCart = cart.filter(item => item.id === product.id);
                  const isInCart = productVariantsInCart.length > 0;

                  // For products without variants, track base product quantity for inline +/- controls
                  const baseProductQuantity = cart
                    .filter(item => item.id === product.id && !item.variant_id)
                    .reduce((sum, item) => sum + item.quantity, 0);
                  
                  return (
                    <div key={product.id} className={`product-card ${isInCart ? 'in-cart' : ''}`}>
                      {isInCart && (
                        <div className="cart-checkmark">✓</div>
                      )}
                      {product.image_url && (
                        <div className="product-image">
                          <img src={product.image_url} alt={product.name} />
                        </div>
                      )}
                      <div className="product-info">
                        <div className="product-category">{product.category_name || 'Uncategorized'}</div>
                        <div className="product-name">{product.name}</div>
                        {hasVariants && (
                          <div className="product-variant-indicator">
                            {hasSizes && hasColors ? 'Sizes & Colors' : hasSizes ? 'Sizes' : 'Colors'}
                          </div>
                        )}
                        <div className="product-price">{formatCurrency(product.price)}</div>
                      </div>
                      <div className="product-actions">
                        {baseProductQuantity > 0 && !hasVariants ? (
                          <div className="quantity-controls-on-card">
                            <button 
                              className="qty-btn-card"
                              onClick={(e) => {
                                e.stopPropagation();
                                const cartItem = cart.find(item => item.id === product.id && !item.variant_id);
                                if (cartItem) updateQuantity(cartItem, -1);
                              }}
                            >-</button>
                            <span className="qty-value-card">{baseProductQuantity}</span>
                            <button 
                              className="qty-btn-card"
                              onClick={(e) => {
                                e.stopPropagation();
                                const cartItem = cart.find(item => item.id === product.id && !item.variant_id);
                                if (cartItem) {
                                  updateQuantity(cartItem, 1);
                                } else {
                                  addToCart(product);
                                }
                              }}
                            >+</button>
                          </div>
                        ) : hasVariants ? (
                          <button 
                            className="add-to-cart-btn" 
                            onClick={(e) => {
                              e.stopPropagation();
                              addToCart(product);
                            }}
                          >
                            Select Variant
                          </button>
                        ) : (
                          <button 
                            className="add-to-cart-btn" 
                            onClick={(e) => {
                              e.stopPropagation();
                              addToCart(product);
                            }}
                          >
                            Add
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Right Sidebar - Order Details */}
        <div className="pos-sidebar-right">
          <div className="order-details">
            <div className="order-list-header">
              <h3>Order List</h3>
              <div className="order-header-right">
                <span className="order-number">{orderNumber}</span>
                {cart.length > 0 && (
                  <button className="trash-btn" onClick={clearCart} title="Delete Order">🗑️</button>
                )}
              </div>
            </div>

            <div className="customer-section">
              <select 
                className="customer-select"
                value={selectedCustomer?.id || ''}
                onChange={(e) => {
                  const customerId = parseInt(e.target.value);
                  const customer = customers.find(c => c.id === customerId);
                  setSelectedCustomer(customer || null);
                }}
              >
                <option value="">Walk in Customer</option>
                {customers.map(customer => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
              {selectedCustomer && (
                <div className="customer-info">
                  <div className="customer-name">{selectedCustomer.name}</div>
                </div>
              )}
            </div>

            <div className="order-details-section">
              <div className="order-details-header" style={{ marginBottom: '1rem' }}>
                <h4 style={{ fontSize: '1.2rem', fontWeight: '700', color: '#111827', margin: '0 0 0.5rem 0' }}>
                  Order Items
                </h4>
                <div className="order-details-header-right" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="items-count" style={{ fontWeight: '600', color: '#667eea', fontSize: '1rem' }}>
                    {getCartItemCount()} {getCartItemCount() === 1 ? 'Item' : 'Items'}
                  </span>
                  {cart.length > 0 && (
                    <button className="clear-all-btn" onClick={clearCart}>Clear all</button>
                  )}
                </div>
              </div>

              <div className="cart-items-table" style={{ 
                display: 'block',
                minHeight: '300px',
                maxHeight: '500px',
                overflowY: 'auto',
                overflowX: 'visible',
                background: 'white',
                borderRadius: '8px',
                padding: '0.75rem',
                border: '1px solid #e5e7eb'
              }}>
                {cart.length === 0 ? (
                  <div className="empty-cart" style={{ 
                    textAlign: 'center', 
                    padding: '3rem 2rem', 
                    color: '#9ca3af',
                    fontSize: '1.1rem',
                    fontWeight: '500'
                  }}>
                    <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🛒</div>
                    <div>Cart is empty</div>
                    <div style={{ fontSize: '0.9rem', marginTop: '0.5rem', color: '#6b7280' }}>
                      Add products to get started
                    </div>
                  </div>
                ) : (
                  <table className="order-items-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                        <th style={{ width: '45%', padding: '0.5rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: '600', color: '#6b7280' }}>Product</th>
                        <th style={{ width: '20%', padding: '0.5rem', textAlign: 'center', fontSize: '0.75rem', fontWeight: '600', color: '#6b7280' }}>QTY</th>
                        <th style={{ width: '25%', padding: '0.5rem', textAlign: 'right', fontSize: '0.75rem', fontWeight: '600', color: '#6b7280' }}>Price</th>
                        <th style={{ width: '10%', padding: '0.5rem', textAlign: 'center', fontSize: '0.75rem', fontWeight: '600', color: '#6b7280' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {cart.map((item, index) => {
                        const cartKey = item.variant_id 
                          ? `${item.id}-${item.variant_id}-${index}` 
                          : `${item.id}-${index}`;
                        
                        const variantInfo = [];
                        if (item.size) variantInfo.push(item.size);
                        if (item.color) variantInfo.push(item.color);
                        const variantStr = variantInfo.length > 0 ? variantInfo.join(', ') : '';
                        const hasVariants = item.variant_id || item.size || item.color;
                        
                        return (
                          <tr key={cartKey} style={{ borderBottom: '1px solid #f3f4f6' }}>
                            <td className="item-name-cell" style={{ padding: '0.5rem' }}>
                              <div className="item-name-main" style={{ fontWeight: '600', fontSize: '0.85rem', marginBottom: '0.15rem', color: '#111827' }}>
                                {item.name}
                              </div>
                              {hasVariants && (
                                <div className="item-variant-info" style={{ fontSize: '0.7rem', color: '#6b7280', marginBottom: '0.1rem' }}>
                                  {variantStr}
                                </div>
                              )}
                              {item.stock_quantity !== undefined && (
                                <div style={{ fontSize: '0.65rem', color: item.stock_quantity > 0 ? '#10b981' : '#ef4444' }}>
                                  {item.stock_quantity}
                                </div>
                              )}
                            </td>
                            <td className="item-qty-cell" style={{ padding: '0.5rem' }}>
                              <div className="qty-controls-table" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}>
                                <button 
                                  onClick={() => updateQuantity(item, -1)} 
                                  className="qty-btn-table"
                                  style={{ 
                                    minWidth: '24px', 
                                    height: '24px', 
                                    border: '1px solid #d1d5db',
                                    borderRadius: '3px',
                                    background: 'white',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: '600',
                                    color: '#374151',
                                    padding: '0'
                                  }}
                                >
                                  -
                                </button>
                                <input
                                  type="number"
                                  min="1"
                                  value={item.quantity}
                                  onChange={(e) => setQuantityDirectly(item, e.target.value)}
                                  onBlur={(e) => {
                                    const val = parseInt(e.target.value) || 1;
                                    setQuantityDirectly(item, val);
                                  }}
                                  className="qty-input-table"
                                  style={{
                                    width: '45px',
                                    textAlign: 'center',
                                    padding: '0.25rem',
                                    border: '1px solid #d1d5db',
                                    borderRadius: '3px',
                                    fontSize: '0.75rem',
                                    fontWeight: '600'
                                  }}
                                />
                                <button 
                                  onClick={() => updateQuantity(item, 1)} 
                                  className="qty-btn-table"
                                  style={{ 
                                    minWidth: '24px', 
                                    height: '24px',
                                    border: '1px solid #d1d5db',
                                    borderRadius: '3px',
                                    background: 'white',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: '600',
                                    color: '#374151',
                                    padding: '0'
                                  }}
                                >
                                  +
                                </button>
                              </div>
                            </td>
                            <td className="item-cost-cell" style={{ padding: '0.5rem', textAlign: 'right' }}>
                              <div style={{ fontWeight: '600', fontSize: '0.85rem', color: '#111827' }}>
                                {formatCurrency(item.price * item.quantity)}
                              </div>
                            </td>
                            <td className="item-actions-cell" style={{ padding: '0.5rem', textAlign: 'center' }}>
                              <button 
                                className="remove-item-btn" 
                                onClick={() => removeFromCart(item)}
                                title="Remove"
                                style={{
                                  background: 'transparent',
                                  color: '#ef4444',
                                  border: 'none',
                                  borderRadius: '4px',
                                  padding: '0.35rem',
                                  cursor: 'pointer',
                                  fontSize: '1rem',
                                  transition: 'background 0.2s',
                                  width: '28px',
                                  height: '28px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center'
                                }}
                                onMouseEnter={(e) => {
                                  e.target.style.background = '#fee2e2';
                                }}
                                onMouseLeave={(e) => {
                                  e.target.style.background = 'transparent';
                                }}
                              >
                                🗑️
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {cart.length > 0 && (
              <>
                {discount > 0 && (
                  <div className="discount-section">
                    <div className="discount-box">
                      <div className="discount-info">
                        <span className="discount-label">Discount {discount}{discountType === 'percentage' ? '%' : ''}</span>
                        <span className="discount-condition">For $20 Minimum Purchase, all Items</span>
                      </div>
                      <button 
                        className="remove-discount-btn"
                        onClick={() => {
                          setDiscount(0);
                          setDiscountType('percentage');
                        }}
                        title="Remove Discount"
                      >🗑️</button>
                    </div>
                  </div>
                )}

                {/* Simple Total Display */}
                <div style={{ 
                  marginTop: '1rem', 
                  padding: '1rem', 
                  background: '#f9fafb', 
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb'
                }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    fontSize: '1.25rem',
                    fontWeight: '700',
                    color: '#111827'
                  }}>
                    <span>Total:</span>
                    <span style={{ color: '#667eea', fontSize: '1.5rem' }}>
                      {formatCurrency(calculateTotal())}
                    </span>
                  </div>
                </div>

                <div className="checkout-actions">
                  <button 
                    className="print-order-btn"
                    onClick={() => {
                      if (lastSale) {
                        setShowReceipt(true);
                      } else {
                        toast.info('Complete an order first to print');
                      }
                    }}
                  >
                    🖨️ Print Order
                  </button>
                  <button 
                    className="place-order-btn"
                    onClick={() => {
                      // Show shipping address modal first
                      setShowShippingModal(true);
                    }}
                  >
                    🛒 Place Order
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Shipping Address Modal */}
      {showShippingModal && (
        <div className="modal-overlay" onClick={() => setShowShippingModal(false)}>
          <div className="modal-content payment-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Shipping Information</h2>
              <button onClick={() => setShowShippingModal(false)} className="close-btn">×</button>
            </div>
            <div className="payment-form">
              <div className="form-group">
                <label>Delivery Method *</label>
                <select
                  value={deliveryMethod}
                  onChange={(e) => {
                    setDeliveryMethod(e.target.value);
                    if (e.target.value === 'pickup') {
                      setDeliveryCost(0);
                    }
                  }}
                >
                  <option value="pickup">Pickup (No Charge)</option>
                  <option value="delivery">Standard Delivery</option>
                  <option value="express">Express Delivery</option>
                </select>
              </div>
              {(deliveryMethod === 'delivery' || deliveryMethod === 'express') && (
                <>
                  <div className="form-group">
                    <label>Shipping Address *</label>
                    <textarea
                      value={shippingAddress}
                      onChange={(e) => setShippingAddress(e.target.value)}
                      placeholder="Enter full shipping address"
                      rows="3"
                      style={{ width: '100%', padding: '0.75rem', border: '1px solid #ddd', borderRadius: '4px', fontSize: '0.95rem' }}
                    />
                  </div>
                  <div className="form-group">
                    <label>Location *</label>
                    <input
                      type="text"
                      value={shippingLocation}
                      onChange={(e) => setShippingLocation(e.target.value)}
                      placeholder="Enter location/area"
                      style={{ width: '100%', padding: '0.75rem', border: '1px solid #ddd', borderRadius: '4px', fontSize: '0.95rem' }}
                    />
                  </div>
                  <div className="form-group">
                    <label>Delivery Cost *</label>
                    <input
                      type="number"
                      value={deliveryCost}
                      onChange={(e) => setDeliveryCost(parseFloat(e.target.value) || 0)}
                      placeholder="Enter delivery cost"
                      step="0.01"
                      min="0"
                    />
                    <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '0.25rem', display: 'block' }}>
                      Enter the delivery charge amount
                    </small>
                  </div>
                  <div className="form-group">
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={hasExtraPayment}
                        onChange={(e) => {
                          setHasExtraPayment(e.target.checked);
                          if (!e.target.checked) {
                            setExtraPaymentAmount(0);
                          }
                        }}
                        style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span>Add Extra Payment</span>
                    </label>
                    {hasExtraPayment && (
                      <input
                        type="number"
                        value={extraPaymentAmount}
                        onChange={(e) => setExtraPaymentAmount(parseFloat(e.target.value) || 0)}
                        placeholder="Enter extra payment amount"
                        step="0.01"
                        min="0"
                        style={{ marginTop: '0.5rem' }}
                      />
                    )}
                    <small style={{ color: '#666', fontSize: '0.85rem', marginTop: '0.25rem', display: 'block' }}>
                      {hasExtraPayment ? 'This amount will be added to the total' : 'Check to add an extra payment amount'}
                    </small>
                  </div>
                </>
              )}
              <div className="form-group">
                <label>Subtotal</label>
                <input
                  type="text"
                  value={formatCurrency(calculateSubtotal())}
                  disabled
                />
              </div>
              {deliveryCost > 0 && (
                <div className="form-group">
                  <label>Delivery Cost</label>
                  <input
                    type="text"
                    value={formatCurrency(deliveryCost)}
                    disabled
                  />
                </div>
              )}
              {hasExtraPayment && extraPaymentAmount > 0 && (
                <div className="form-group">
                  <label>Extra Payment</label>
                  <input
                    type="text"
                    value={formatCurrency(extraPaymentAmount)}
                    disabled
                    style={{ color: '#667eea', fontWeight: '600' }}
                  />
                </div>
              )}
              <div className="form-group">
                <label>Total Amount</label>
                <input
                  type="text"
                  value={formatCurrency(calculateTotal())}
                  disabled
                  style={{ fontWeight: 'bold', fontSize: '1.1rem' }}
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => setShowShippingModal(false)} className="btn-cancel">Cancel</button>
                <button 
                  onClick={() => {
                    if ((deliveryMethod === 'delivery' || deliveryMethod === 'express')) {
                      if (!shippingAddress.trim()) {
                        toast.warning('Please enter shipping address');
                        return;
                      }
                      if (!shippingLocation.trim()) {
                        toast.warning('Please enter location');
                        return;
                      }
                      if (deliveryCost <= 0) {
                        toast.warning('Please enter delivery cost');
                        return;
                      }
                    }
                    setShowShippingModal(false);
                    // Always show payment modal after shipping details
                    setShowPaymentModal(true);
                  }} 
                  className="btn-submit"
                >
                  Continue to Payment
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="modal-overlay" onClick={() => setShowPaymentModal(false)}>
          <div className="modal-content payment-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Complete Payment</h2>
              <button onClick={() => setShowPaymentModal(false)} className="close-btn">×</button>
            </div>
            <div className="payment-form">
              <div className="form-group">
                <label>Payment Method *</label>
                <div className="payment-methods-grid" style={{ marginTop: '0.5rem' }}>
                  <button
                    className={`payment-method-btn ${paymentMethod === 'cash' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('cash')}
                    style={paymentMethod === 'cash' ? { borderColor: '#10b981', backgroundColor: '#10b98115' } : {}}
                  >
                    <span className="payment-icon" style={{ color: '#10b981' }}>💵</span>
                    <span>Cash</span>
                  </button>
                  <button
                    className={`payment-method-btn ${paymentMethod === 'mpesa' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('mpesa')}
                    style={paymentMethod === 'mpesa' ? { borderColor: '#10b981', backgroundColor: '#10b98115' } : {}}
                  >
                    <span className="payment-icon" style={{ color: '#10b981' }}>📱</span>
                    <span>Mobile Money</span>
                  </button>
                </div>
              </div>
              {(paymentMethod === 'cash' || paymentMethod === 'mpesa') && (
                <>
                  <div className="form-group">
                    <label>Received Amount *</label>
                    <input
                      type="number"
                      value={receivedAmount}
                      onChange={(e) => setReceivedAmount(e.target.value)}
                      placeholder="Enter amount received"
                      step="0.01"
                      min="0"
                    />
                  </div>
                  <div className="quick-cash">
                    <button 
                      className="exact-btn"
                      onClick={() => setReceivedAmount(calculateTotal().toFixed(2))}
                    >
                      Exact
                    </button>
                  </div>
                  {change > 0 && (
                    <div className="change-display">
                      <strong>Change: {formatCurrency(change)}</strong>
                    </div>
                  )}
                </>
              )}
              {(deliveryMethod === 'delivery' || deliveryMethod === 'express') && (
                <>
                  {shippingAddress && (
                    <div className="form-group">
                      <label>Shipping Address</label>
                      <input
                        type="text"
                        value={shippingAddress}
                        disabled
                        style={{ fontSize: '0.9rem', color: '#666' }}
                      />
                    </div>
                  )}
                  {shippingLocation && (
                    <div className="form-group">
                      <label>Location</label>
                      <input
                        type="text"
                        value={shippingLocation}
                        disabled
                        style={{ fontSize: '0.9rem', color: '#666' }}
                      />
                    </div>
                  )}
                </>
              )}
              <div className="form-group">
                <label>Subtotal</label>
                <input
                  type="text"
                  value={formatCurrency(calculateSubtotal())}
                  disabled
                />
              </div>
              {deliveryCost > 0 && (
                <div className="form-group">
                  <label>Delivery ({deliveryMethod === 'delivery' ? 'Standard' : 'Express'})</label>
                  <input
                    type="text"
                    value={formatCurrency(deliveryCost)}
                    disabled
                  />
                </div>
              )}
              {hasExtraPayment && extraPaymentAmount > 0 && (
                <div className="form-group">
                  <label>Extra Payment</label>
                  <input
                    type="text"
                    value={formatCurrency(extraPaymentAmount)}
                    disabled
                    style={{ color: '#667eea', fontWeight: '600' }}
                  />
                </div>
              )}
              <div className="form-group">
                <label>Total Amount</label>
                <input
                  type="text"
                  value={formatCurrency(calculateTotal())}
                  disabled
                  style={{ fontWeight: 'bold', fontSize: '1.1rem' }}
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => {
                  setShowPaymentModal(false);
                  setShowShippingModal(true);
                }} className="btn-cancel">Back</button>
                <button 
                  onClick={handlePayment} 
                  className="btn-submit"
                  disabled={(paymentMethod === 'cash' || paymentMethod === 'mpesa') && (!receivedAmount || parseFloat(receivedAmount) < calculateTotal())}
                >
                  Complete Order
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Success Modal */}
      {showSuccessModal && lastSale && (
        <div className="modal-overlay" onClick={() => setShowSuccessModal(false)}>
          <div className="modal-content success-modal" onClick={(e) => e.stopPropagation()}>
            <div className="success-content">
              <div className="success-icon">✓</div>
              <h2>Congratulations, Sale Completed</h2>
              <div className="sale-details">
                <p><strong>Bill Amount:</strong> {formatCurrency(lastSale.total)}</p>
                {lastSale.change > 0 && (
                  <p><strong>Change:</strong> {formatCurrency(lastSale.change)}</p>
                )}
              </div>
              <div className="success-actions">
                <button onClick={() => {
                  setShowSuccessModal(false);
                  setShowReceipt(true);
                }}>Print Receipt</button>
                <button onClick={() => {
                  setShowSuccessModal(false);
                  setLastSale(null);
                }}>Next Order</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Receipt Modal */}
      {showReceipt && lastSale && (
        <Receipt 
          sale={lastSale} 
          onClose={() => {
            setShowReceipt(false);
            setLastSale(null);
          }} 
        />
      )}

      {/* Variant Selector Modal */}
      {showVariantSelector && selectedProduct && (
        <VariantSelector
          product={selectedProduct}
          onSelect={addProductToCart}
          onClose={() => {
            setShowVariantSelector(false);
            setSelectedProduct(null);
          }}
        />
      )}

      {/* Confirm Clear Cart Dialog */}
      <ConfirmDialog
        isOpen={showConfirmClear}
        title="Clear Cart"
        message="Clear all items from cart?"
        onConfirm={confirmClearCart}
        onCancel={() => setShowConfirmClear(false)}
        confirmText="Clear"
        cancelText="Cancel"
        type="danger"
      />
    </div>
  );
};

export default POS;
