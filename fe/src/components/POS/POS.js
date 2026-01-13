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
  const [coupon, setCoupon] = useState(0);
  const [roundoff, setRoundoff] = useState(false);
  const [featuredFilter, setFeaturedFilter] = useState(false);
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
    
    if (existingItem) {
      setCart(cart.map(item => {
        const itemKey = item.variant_id 
          ? `${item.id}-${item.variant_id}` 
          : `${item.id}`;
        if (itemKey === cartKey) {
          return { ...item, quantity: item.quantity + 1 };
        }
        return item;
      }));
    } else {
      setCart([...cart, {
        ...product,
        quantity: 1,
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
    const totalBeforeRoundoff = subtotal - discountAmount - coupon + taxAmount + shipping;
    const rounded = Math.round(totalBeforeRoundoff);
    return rounded - totalBeforeRoundoff;
  };

  const calculateTotal = () => {
    const subtotal = calculateSubtotal();
    const discountAmount = calculateDiscountAmount();
    const taxAmount = calculateTaxAmount();
    const roundoffAmount = calculateRoundoff();
    return subtotal - discountAmount - coupon + taxAmount + shipping + roundoffAmount;
  };

  const handlePayment = async () => {
    if (cart.length === 0) {
      toast.warning('Cart is empty');
      return;
    }

    const total = calculateTotal();
    const received = parseFloat(receivedAmount) || 0;
    
    if ((paymentMethod === 'cash' || paymentMethod === 'mpesa') && received < total) {
      toast.warning('Received amount is less than total');
      return;
    }

    try {
      const subtotal = calculateSubtotal();
      const discountAmount = calculateDiscountAmount();
      const taxAmount = (subtotal - discountAmount) * (tax / 100);
      const finalTotal = subtotal - discountAmount + taxAmount + shipping;
      
      const saleData = {
        items: cart.map(item => ({
          product_id: item.id,
          variant_id: item.variant_id || null,
          quantity: item.quantity,
          unit_price: parseFloat(item.price),
        })),
        tax_amount: parseFloat(taxAmount.toFixed(2)),
        discount_amount: parseFloat(discountAmount.toFixed(2)),
        payment_method: paymentMethod,
        amount_paid: (paymentMethod === 'cash' || paymentMethod === 'mpesa') ? parseFloat(received.toFixed(2)) : parseFloat(finalTotal.toFixed(2)),
        notes: '',
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
          ? Math.max(0, received - finalTotal) 
          : 0
      };
      setLastSale(saleWithChange);
      setCart([]);
      setShowPaymentModal(false);
      setShowSuccessModal(true);
      setReceivedAmount('');
      setShipping(0);
      setTax(0);
      setDiscount(0);
      toast.success('Sale completed successfully');
    } catch (error) {
      toast.error('Failed to complete sale: ' + (error.response?.data?.error || error.message));
    }
  };

  const getCartItemCount = () => {
    return cart.reduce((sum, item) => sum + item.quantity, 0);
  };

  const isProductInCart = (productId, variantId = null) => {
    return cart.some(item => {
      if (item.id !== productId) return false;
      // If variantId is provided, check for exact match
      if (variantId !== null) {
        return item.variant_id === variantId;
      }
      // If no variantId provided, check if product has any variant in cart
      // This is for products without variants
      return !item.variant_id;
    });
  };

  const getProductQuantity = (productId, variantId = null) => {
    const item = cart.find(item => {
      if (item.id !== productId) return false;
      if (variantId !== null) {
        return item.variant_id === variantId;
      }
      return !item.variant_id;
    });
    return item ? item.quantity : 0;
  };

  const paymentMethods = [
    { id: 'cash', label: 'Cash', icon: '💵', color: '#10b981' },
    { id: 'deposit', label: 'Deposit', icon: '📦', color: '#f97316' },
    { id: 'pay_later', label: 'Pay Later', icon: '📅', color: '#f97316' },
    { id: 'external', label: 'External', icon: '🔗', color: '#a855f7' },
    { id: 'mpesa', label: 'Mobile Money', icon: '📱', color: '#10b981' },
  ];

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
                  
                  // For products with variants, we can't use simple inCart check
                  // Instead, check if any variant of this product is in cart
                  const productVariantsInCart = cart.filter(item => item.id === product.id);
                  const inCart = productVariantsInCart.length > 0;
                  const totalQuantity = productVariantsInCart.reduce((sum, item) => sum + item.quantity, 0);
                  
                  // Get quantity for this specific product (base product, not variants)
                  const baseProductQuantity = cart
                    .filter(item => item.id === product.id && !item.variant_id)
                    .reduce((sum, item) => sum + item.quantity, 0);
                  
                  return (
                    <div key={product.id} className={`product-card ${baseProductQuantity > 0 ? 'in-cart' : ''}`}>
                      {baseProductQuantity > 0 && (
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
              <div className="order-details-header">
                <h4>Order Details</h4>
                <div className="order-details-header-right">
                  <span className="items-count">Items: {getCartItemCount()}</span>
                  {cart.length > 0 && (
                    <button className="clear-all-btn" onClick={clearCart}>Clear all</button>
                  )}
                </div>
              </div>

              <div className="cart-items-table">
                {cart.length === 0 ? (
                  <div className="empty-cart">Cart is empty</div>
                ) : (
                  <table className="order-items-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>QTY</th>
                        <th>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cart.map((item, index) => {
                        const cartKey = item.variant_id 
                          ? `${item.id}-${item.variant_id}-${index}` 
                          : `${item.id}-${index}`;
                        
                        const variantInfo = [];
                        if (item.size) variantInfo.push(`Size: ${item.size}`);
                        if (item.color) variantInfo.push(`Color: ${item.color}`);
                        const variantStr = variantInfo.length > 0 ? ` (${variantInfo.join(', ')})` : '';
                        
                        return (
                          <tr key={cartKey}>
                            <td className="item-name-cell">
                              <div className="item-name-main">{item.name}{variantStr}</div>
                              {item.sku && <div className="item-sku">SKU: {item.sku}</div>}
                            </td>
                            <td className="item-qty-cell">
                              <div className="qty-controls-table">
                                <button onClick={() => updateQuantity(item, -1)} className="qty-btn-table">-</button>
                                <span className="qty-value-table">{item.quantity}</span>
                                <button onClick={() => updateQuantity(item, 1)} className="qty-btn-table">+</button>
                              </div>
                            </td>
                            <td className="item-cost-cell">
                              {formatCurrency(item.price * item.quantity)}
                              <button 
                                className="remove-item-btn" 
                                onClick={() => removeFromCart(item)}
                                title="Remove"
                              >×</button>
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

                <div className="payment-summary-section">
                  <div className="payment-summary-header">Payment Summary</div>
                  <div className="payment-summary-content">
                    <div className="summary-row">
                      <span>Shipping:</span>
                      <span>{formatCurrency(shipping)}</span>
                    </div>
                    <div className="summary-row">
                      <span>Tax:</span>
                      <span>{formatCurrency(calculateTaxAmount())}</span>
                    </div>
                    {coupon > 0 && (
                      <div className="summary-row">
                        <span>Coupon:</span>
                        <span>-{formatCurrency(coupon)}</span>
                      </div>
                    )}
                    {discount > 0 && (
                      <div className="summary-row discount-row">
                        <span>Discount:</span>
                        <span>-{formatCurrency(calculateDiscountAmount())}</span>
                      </div>
                    )}
                    <div className="summary-row roundoff-row">
                      <span>Roundoff:</span>
                      <div className="roundoff-control">
                        <span>{formatCurrency(calculateRoundoff())}</span>
                        <label className="roundoff-toggle">
                          <input
                            type="checkbox"
                            checked={roundoff}
                            onChange={(e) => setRoundoff(e.target.checked)}
                          />
                          <span className="toggle-slider"></span>
                        </label>
                      </div>
                    </div>
                    <div className="summary-row subtotal-row">
                      <span>Sub Total:</span>
                      <span>{formatCurrency(calculateSubtotal())}</span>
                    </div>
                    <div className="summary-row total-payable-row">
                      <span>Total Payable:</span>
                      <span className="total-payable-amount">{formatCurrency(calculateTotal())}</span>
                    </div>
                  </div>
                </div>

                <div className="payment-methods-section">
                  <div className="payment-methods-label">Select Payment</div>
                  <div className="payment-methods-grid">
                    {paymentMethods.map(method => (
                      <button
                        key={method.id}
                        className={`payment-method-btn ${paymentMethod === method.id ? 'active' : ''}`}
                        onClick={() => setPaymentMethod(method.id)}
                        style={paymentMethod === method.id && method.color ? { borderColor: method.color, backgroundColor: `${method.color}15` } : {}}
                      >
                        <span className="payment-icon" style={method.color ? { color: method.color } : {}}>{method.icon}</span>
                        <span>{method.label}</span>
                      </button>
                    ))}
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
                      if (paymentMethod === 'cash' || paymentMethod === 'mpesa') {
                        setShowPaymentModal(true);
                      } else {
                        handlePayment();
                      }
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

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="modal-overlay" onClick={() => setShowPaymentModal(false)}>
          <div className="modal-content payment-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Finalize Sale</h2>
              <button onClick={() => setShowPaymentModal(false)} className="close-btn">×</button>
            </div>
            <div className="payment-form">
              <div className="form-group">
                <label>Payment Type *</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                >
                  {paymentMethods.map(method => (
                    <option key={method.id} value={method.id}>{method.label}</option>
                  ))}
                </select>
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
              <div className="form-group">
                <label>Total Amount</label>
                <input
                  type="text"
                  value={formatCurrency(calculateTotal())}
                  disabled
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => setShowPaymentModal(false)} className="btn-cancel">Cancel</button>
                <button onClick={handlePayment} className="btn-submit">Complete Sale</button>
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
