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

  useEffect(() => {
    loadProductDetails();
    loadVariants();
  }, [product]);

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
      });
    } else if (!product.has_variants) {
      // Product without variants - add directly
      onSelect({
        ...product,
        price: parseFloat(product.price),
        sku: product.sku || '',
        stock_quantity: product.stock_quantity || 0,
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
                    <span>Price:</span>
                    <strong>{formatCurrency(getVariantPrice())}</strong>
                  </div>
                  <div className="variant-detail-row">
                    <span>Stock:</span>
                    <strong className={getVariantStock() === 0 ? 'out-of-stock' : ''}>
                      {getVariantStock()} {product.unit || 'pcs'}
                    </strong>
                  </div>
                  {selectedVariant.sku && (
                    <div className="variant-detail-row">
                      <span>SKU:</span>
                      <span className="variant-sku">{selectedVariant.sku}</span>
                    </div>
                  )}
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

