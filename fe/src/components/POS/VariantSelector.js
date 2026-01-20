import React, { useState, useEffect } from 'react';
import { variantsAPI, sizesAPI, colorsAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import './VariantSelector.css';

const VariantSelector = ({ product, onSelect, onClose }) => {
  const [variants, setVariants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [selectedSize, setSelectedSize] = useState(null);
  const [selectedColor, setSelectedColor] = useState(null);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [availableSizes, setAvailableSizes] = useState([]);
  const [availableColors, setAvailableColors] = useState([]);
  const [quantity, setQuantity] = useState(1);
  const [quantityInput, setQuantityInput] = useState('1');
  const [quantityError, setQuantityError] = useState(null);

  useEffect(() => {
    loadProductDetails();
    loadVariants();
  }, [product]);

  // Sync quantityInput with quantity when quantity changes externally
  useEffect(() => {
    setQuantityInput(quantity.toString());
    setQuantityError(null); // Clear any errors when quantity changes externally
  }, [quantity]);

  const loadProductDetails = async () => {
    setLoadingDetails(true);
    try {
      // Always fetch full product details to ensure we have sizes and colors
      const response = await productsAPI.get(product.id);
      const fullProduct = response.data;
      
      console.log('[VariantSelector] Full product data:', {
        id: fullProduct.id,
        name: fullProduct.name,
        has_variants: fullProduct.has_variants,
        sizes_count: fullProduct.available_sizes_detail?.length || 0,
        colors_count: fullProduct.available_colors_detail?.length || 0,
        sizes: fullProduct.available_sizes_detail,
        colors: fullProduct.available_colors_detail
      });
      
      // Set sizes - check both available_sizes_detail and available_sizes
      const sizes = fullProduct.available_sizes_detail || fullProduct.available_sizes || [];
      if (sizes.length > 0) {
        setAvailableSizes(Array.isArray(sizes) ? sizes : []);
        console.log('[VariantSelector] Set sizes:', sizes.length);
      } else if (product.available_sizes_detail && product.available_sizes_detail.length > 0) {
        // Fallback to product prop if API doesn't return it
        setAvailableSizes(product.available_sizes_detail);
        console.log('[VariantSelector] Using fallback sizes from product prop');
      } else if (product.available_sizes && product.available_sizes.length > 0) {
        setAvailableSizes(product.available_sizes);
        console.log('[VariantSelector] Using fallback sizes (array) from product prop');
      }
      
      // Set colors - check both available_colors_detail and available_colors
      const colors = fullProduct.available_colors_detail || fullProduct.available_colors || [];
      if (colors.length > 0) {
        setAvailableColors(Array.isArray(colors) ? colors : []);
        console.log('[VariantSelector] Set colors:', colors.length);
      } else if (product.available_colors_detail && product.available_colors_detail.length > 0) {
        // Fallback to product prop if API doesn't return it
        setAvailableColors(product.available_colors_detail);
        console.log('[VariantSelector] Using fallback colors from product prop');
      } else if (product.available_colors && product.available_colors.length > 0) {
        setAvailableColors(product.available_colors);
        console.log('[VariantSelector] Using fallback colors (array) from product prop');
      }
    } catch (error) {
      console.error('[VariantSelector] Error loading product details:', error);
      // Fallback to product prop data
      if (product.available_sizes_detail && product.available_sizes_detail.length > 0) {
        setAvailableSizes(product.available_sizes_detail);
      } else if (product.available_sizes && product.available_sizes.length > 0) {
        setAvailableSizes(product.available_sizes);
      }
      if (product.available_colors_detail && product.available_colors_detail.length > 0) {
        setAvailableColors(product.available_colors_detail);
      } else if (product.available_colors && product.available_colors.length > 0) {
        setAvailableColors(product.available_colors);
      }
    } finally {
      setLoadingDetails(false);
    }
  };

  const loadVariants = async () => {
    try {
      const response = await variantsAPI.getByProduct(product.id);
      const variantsData = response.data.results || response.data || [];
      setVariants(variantsData);
      
      // If no variants exist but product has sizes/colors, we can still proceed
      // The user can add the product without a variant (using base product)
      if (variantsData.length === 0 && (product.available_sizes?.length > 0 || product.available_colors?.length > 0)) {
        // Product has variants enabled but no variants created yet
        // Allow adding base product
      }
    } catch (error) {
      console.error('Error loading variants:', error);
      // If error, still allow proceeding with base product
    } finally {
      setLoading(false);
    }
  };

  const handleSizeSelect = (sizeId) => {
    setSelectedSize(sizeId);
    setSelectedColor(null);
    setSelectedVariant(null);
  };

  const handleColorSelect = (colorId) => {
    setSelectedColor(colorId);
    setSelectedVariant(null);
  };

  // Find variant based on selected size and color
  useEffect(() => {
    console.log('[VariantSelector] Variant matching effect:', {
      variantsCount: variants.length,
      availableSizes: availableSizes.length,
      availableColors: availableColors.length,
      selectedSize,
      selectedColor
    });

    if (variants.length === 0) {
      // No variants created yet, allow adding base product
      setSelectedVariant(null);
      return;
    }
    
    // If both sizes and colors are available, require both selections
    if (availableSizes.length > 0 && availableColors.length > 0) {
      if (selectedSize && selectedColor) {
        const variant = variants.find(v => {
          // Handle both ID and object formats for size
          const sizeMatch = v.size === selectedSize || 
                          v.size_id === selectedSize || 
                          (typeof v.size === 'object' && v.size?.id === selectedSize) ||
                          (typeof v.size === 'number' && v.size === selectedSize);
          // Handle both ID and object formats for color
          const colorMatch = v.color === selectedColor || 
                           v.color_id === selectedColor || 
                           (typeof v.color === 'object' && v.color?.id === selectedColor) ||
                           (typeof v.color === 'number' && v.color === selectedColor);
          return sizeMatch && colorMatch;
        });
        console.log('[VariantSelector] Found variant for size+color:', variant);
        setSelectedVariant(variant || null);
      } else {
        setSelectedVariant(null);
      }
    }
    // If only sizes are available, require size selection
    else if (availableSizes.length > 0 && availableColors.length === 0) {
      if (selectedSize) {
        const variant = variants.find(v => {
          const sizeMatch = v.size === selectedSize || 
                          v.size_id === selectedSize || 
                          (typeof v.size === 'object' && v.size?.id === selectedSize) ||
                          (typeof v.size === 'number' && v.size === selectedSize);
          return sizeMatch && (!v.color && !v.color_id);
        });
        console.log('[VariantSelector] Found variant for size only:', variant);
        setSelectedVariant(variant || null);
      } else {
        setSelectedVariant(null);
      }
    }
    // If only colors are available, require color selection
    else if (availableColors.length > 0 && availableSizes.length === 0) {
      if (selectedColor) {
        const variant = variants.find(v => {
          const colorMatch = v.color === selectedColor || 
                           v.color_id === selectedColor || 
                           (typeof v.color === 'object' && v.color?.id === selectedColor) ||
                           (typeof v.color === 'number' && v.color === selectedColor);
          return colorMatch && (!v.size && !v.size_id);
        });
        console.log('[VariantSelector] Found variant for color only:', variant);
        setSelectedVariant(variant || null);
      } else {
        setSelectedVariant(null);
      }
    }
    // No size/color options, allow base product
    else {
      setSelectedVariant(null);
    }
  }, [selectedSize, selectedColor, variants, availableSizes.length, availableColors.length]);

  const handleAddToCart = () => {
    const qty = Math.max(1, parseInt(quantity) || 1);
    if (selectedVariant) {
      onSelect({
        ...product,
        variant_id: selectedVariant.id,
        variant: selectedVariant,
        size: selectedVariant.size_name,
        size_id: selectedVariant.size,
        color: selectedVariant.color_name,
        color_id: selectedVariant.color,
        price: parseFloat(selectedVariant.effective_price || selectedVariant.price || product.price),
        stock_quantity: selectedVariant.stock_quantity,
        sku: selectedVariant.sku || product.sku || '',
        quantity: qty,
      });
    } else if (!product.has_variants) {
      // Product without variants - add directly
      onSelect({
        ...product,
        price: parseFloat(product.price),
        sku: product.sku || '',
        stock_quantity: product.stock_quantity || 0,
        quantity: qty,
      });
    }
  };

  const canAddToCart = () => {
    if (!product.has_variants) return true;
    // If no variants exist, allow adding base product
    if (variants.length === 0) return true;
    // If both sizes and colors are available, require both selections
    if (availableSizes.length > 0 && availableColors.length > 0) {
      return selectedSize !== null && selectedColor !== null && selectedVariant !== null;
    }
    // If only sizes are available, require size selection
    if (availableSizes.length > 0 && availableColors.length === 0) {
      return selectedSize !== null && selectedVariant !== null;
    }
    // If only colors are available, require color selection
    if (availableColors.length > 0 && availableSizes.length === 0) {
      return selectedColor !== null && selectedVariant !== null;
    }
    // No size/color options, allow base product
    return true;
  };

  const getVariantStock = () => {
    if (selectedVariant) {
      return selectedVariant.stock_quantity;
    }
    return product.stock_quantity || 0;
  };

  const getVariantPrice = () => {
    if (selectedVariant) {
      return selectedVariant.effective_price || selectedVariant.price || product.price;
    }
    return product.price;
  };

  const validateAndSetQuantity = (inputValue) => {
    // Clear previous error
    setQuantityError(null);

    // Handle empty or invalid input
    if (inputValue === '' || inputValue === '-' || inputValue === null || inputValue === undefined) {
      setQuantity(1);
      setQuantityInput('1');
      return;
    }

    // Parse the input value
    const numValue = parseInt(inputValue);
    
    // Check if it's a valid number
    if (isNaN(numValue)) {
      setQuantityError('Please enter a valid number');
      setQuantity(1);
      setQuantityInput('1');
      return;
    }

    const maxStock = getVariantStock();
    const minValue = 1;

    // Check lower bound
    if (numValue < minValue) {
      setQuantityError(`Minimum quantity is ${minValue}`);
      const finalVal = minValue;
      setQuantity(finalVal);
      setQuantityInput(finalVal.toString());
      return;
    }

    // Check upper bound (if stock is tracked)
    if (maxStock > 0 && numValue > maxStock) {
      setQuantityError(`Maximum quantity is ${maxStock} (stock available)`);
      const finalVal = maxStock;
      setQuantity(finalVal);
      setQuantityInput(finalVal.toString());
      return;
    }

    // Valid value - set it
    setQuantity(numValue);
    setQuantityInput(numValue.toString());
  };

  if (!product.has_variants && variants.length === 0) {
    // No variants, add directly
    handleAddToCart();
    return null;
  }

  return (
    <div className="variant-selector-overlay" onClick={onClose}>
      <div className="variant-selector-modal" onClick={(e) => e.stopPropagation()}>
        <div className="variant-selector-header">
          <h3>Select Variant</h3>
          <button className="variant-selector-close" onClick={onClose}>×</button>
        </div>

        <div className="variant-selector-content">
          <div className="variant-product-info">
            <h4>{product.name}</h4>
            {product.category_name && (
              <span className="variant-category">{product.category_name}</span>
            )}
            {product.subcategory_name && (
              <span className="variant-subcategory">→ {product.subcategory_name}</span>
            )}
          </div>

          {loading || loadingDetails ? (
            <div className="variant-loading">Loading variants...</div>
          ) : (
            <>
              {/* Debug info - remove in production */}
              {process.env.NODE_ENV === 'development' && (
                <div style={{ padding: '10px', background: '#f0f0f0', marginBottom: '10px', fontSize: '12px' }}>
                  <div>Available Sizes: {availableSizes.length}</div>
                  <div>Available Colors: {availableColors.length}</div>
                  <div>Variants: {variants.length}</div>
                  <div>Selected Size: {selectedSize}</div>
                  <div>Selected Color: {selectedColor}</div>
                </div>
              )}

              {availableSizes.length > 0 ? (
                <div className="variant-section">
                  <label>Size</label>
                  <div className="variant-options">
                    {availableSizes.map(size => (
                      <button
                        key={size.id}
                        className={`variant-option ${selectedSize === size.id ? 'selected' : ''}`}
                        onClick={() => handleSizeSelect(size.id)}
                      >
                        {size.name} {size.code ? `(${size.code})` : ''}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {availableColors.length > 0 ? (
                <div className="variant-section">
                  <label>Color</label>
                  <div className="variant-options">
                    {availableColors.map(color => (
                      <button
                        key={color.id}
                        className={`variant-option color-option ${selectedColor === color.id ? 'selected' : ''}`}
                        onClick={() => handleColorSelect(color.id)}
                        style={color.hex_code ? { borderLeftColor: color.hex_code } : {}}
                      >
                        {color.name}
                        {color.hex_code && (
                          <span
                            className="color-swatch"
                            style={{ backgroundColor: color.hex_code }}
                          />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {selectedVariant && (
                <div className="variant-details">
                  <div className="variant-detail-row">
                    <strong>{formatCurrency(getVariantPrice())}</strong>
                  </div>
                  <div className="variant-detail-row">
                    <span className={getVariantStock() === 0 ? 'out-of-stock' : ''}>
                      {getVariantStock()} {product.unit || 'pcs'}
                    </span>
                  </div>
                </div>
              )}

              {!selectedVariant && product.has_variants && variants.length > 0 && (
                <div className="variant-message">
                  {availableSizes.length > 0 && availableColors.length > 0 && (
                    <span>Please select both size and color</span>
                  )}
                  {availableSizes.length > 0 && availableColors.length === 0 && (
                    <span>Please select a size</span>
                  )}
                  {availableColors.length > 0 && availableSizes.length === 0 && (
                    <span>Please select a color</span>
                  )}
                  {availableSizes.length === 0 && availableColors.length === 0 && (
                    <span>No variants available</span>
                  )}
                </div>
              )}

              {/* Quantity Selection - Always show */}
              <div className="variant-section" style={{ marginTop: '1rem' }}>
                <label style={{ fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.5rem', display: 'block' }}>
                  Quantity
                  {getVariantStock() > 0 && (
                    <span style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: '400', marginLeft: '0.5rem' }}>
                      (1 - {getVariantStock()})
                    </span>
                  )}
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                      onClick={() => {
                        const newQty = Math.max(1, quantity - 1);
                        setQuantity(newQty);
                        setQuantityInput(newQty.toString());
                        setQuantityError(null);
                      }}
                      style={{
                        minWidth: '36px',
                        height: '36px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        background: 'white',
                        cursor: 'pointer',
                        fontSize: '1.1rem',
                        fontWeight: '600',
                        color: '#374151',
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.borderColor = '#667eea';
                        e.target.style.background = '#f0f4ff';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.borderColor = '#d1d5db';
                        e.target.style.background = 'white';
                      }}
                    >
                      -
                    </button>
                    <input
                      type="number"
                      min="1"
                      max={getVariantStock() > 0 ? getVariantStock() : undefined}
                      value={quantityInput}
                      onChange={(e) => {
                        // Allow free typing - store raw input value
                        const inputValue = e.target.value;
                        setQuantityInput(inputValue);
                        // Clear error while typing
                        setQuantityError(null);
                      }}
                      onFocus={(e) => {
                        // Select all text on focus for easy replacement
                        e.target.select();
                        // Sync input with current quantity
                        setQuantityInput(quantity.toString());
                        setQuantityError(null);
                      }}
                      onBlur={(e) => {
                        // Validate and clamp on blur
                        validateAndSetQuantity(e.target.value.trim());
                      }}
                      onKeyDown={(e) => {
                        // Allow Enter to blur and validate
                        if (e.key === 'Enter') {
                          e.target.blur();
                        }
                        // Allow Escape to cancel and reset
                        if (e.key === 'Escape') {
                          setQuantityInput(quantity.toString());
                          setQuantityError(null);
                          e.target.blur();
                        }
                      }}
                      style={{
                        width: '120px',
                        textAlign: 'center',
                        padding: '0.75rem',
                        border: `2px solid ${quantityError ? '#ef4444' : '#667eea'}`,
                        borderRadius: '4px',
                        fontSize: '1.1rem',
                        fontWeight: '700',
                        color: quantityError ? '#ef4444' : '#111827',
                        outline: 'none',
                        backgroundColor: quantityError ? '#fef2f2' : '#f9fafb',
                        transition: 'all 0.2s'
                      }}
                      autoFocus={false}
                    />
                    <button
                      onClick={() => {
                        const maxStock = getVariantStock();
                        let newQty;
                        if (maxStock > 0) {
                          newQty = Math.min(quantity + 1, maxStock);
                        } else {
                          newQty = quantity + 1;
                        }
                        setQuantity(newQty);
                        setQuantityInput(newQty.toString());
                        setQuantityError(null);
                      }}
                      disabled={getVariantStock() > 0 && quantity >= getVariantStock()}
                      style={{
                        minWidth: '36px',
                        height: '36px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        background: 'white',
                        cursor: getVariantStock() > 0 && quantity >= getVariantStock() ? 'not-allowed' : 'pointer',
                        fontSize: '1.1rem',
                        fontWeight: '600',
                        color: '#374151',
                        opacity: getVariantStock() > 0 && quantity >= getVariantStock() ? 0.5 : 1,
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        if (!(getVariantStock() > 0 && quantity >= getVariantStock())) {
                          e.target.style.borderColor = '#667eea';
                          e.target.style.background = '#f0f4ff';
                        }
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.borderColor = '#d1d5db';
                        e.target.style.background = 'white';
                      }}
                    >
                      +
                    </button>
                  </div>
                  {quantityError && (
                    <div style={{
                      fontSize: '0.8rem',
                      color: '#ef4444',
                      padding: '0.5rem',
                      background: '#fef2f2',
                      borderRadius: '4px',
                      border: '1px solid #fecaca'
                    }}>
                      {quantityError}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="variant-selector-footer">
          <button className="variant-cancel-btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className="variant-add-btn"
            onClick={handleAddToCart}
            disabled={!canAddToCart() || getVariantStock() === 0}
          >
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  );
};

export default VariantSelector;

