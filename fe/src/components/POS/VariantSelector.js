import React, { useState, useEffect } from 'react';
import { variantsAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

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
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-md flex-col rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">Select Variant</h3>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mb-4 border-b pb-4">
            <h4 className="mb-1 text-base font-medium">{product.name}</h4>
            {product.category_name && (
              <span className="mr-2 text-sm text-muted-foreground">{product.category_name}</span>
            )}
            {product.subcategory_name && (
              <span className="text-sm text-muted-foreground">→ {product.subcategory_name}</span>
            )}
          </div>

          {loading || loadingDetails ? (
            <div className="py-8 text-center text-muted-foreground">Loading variants...</div>
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
                <div className="mb-4">
                  <label className="mb-2 block text-sm font-semibold">Size</label>
                  <div className="flex flex-wrap gap-2">
                    {availableSizes.map(size => (
                      <button
                        key={size.id}
                        type="button"
                        className={cn(
                          'rounded-md border-2 px-3 py-2 text-sm font-medium transition-colors',
                          selectedSize === size.id
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border bg-background hover:border-primary/50 hover:bg-primary/5'
                        )}
                        onClick={() => handleSizeSelect(size.id)}
                      >
                        {size.name} {size.code ? `(${size.code})` : ''}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {availableColors.length > 0 ? (
                <div className="mb-4">
                  <label className="mb-2 block text-sm font-semibold">Color</label>
                  <div className="flex flex-wrap gap-2">
                    {availableColors.map(color => (
                      <button
                        key={color.id}
                        type="button"
                        className={cn(
                          'inline-flex items-center gap-2 rounded-md border-2 border-l-4 px-3 py-2 text-sm font-medium transition-colors',
                          selectedColor === color.id
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border bg-background hover:border-primary/50 hover:bg-primary/5'
                        )}
                        onClick={() => handleColorSelect(color.id)}
                        style={color.hex_code ? { borderLeftColor: color.hex_code } : undefined}
                      >
                        {color.name}
                        {color.hex_code && (
                          <span
                            className="inline-block h-5 w-5 rounded border border-border"
                            style={{ backgroundColor: color.hex_code }}
                          />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {selectedVariant && (
                <div className="mt-4 rounded-md bg-muted/40 p-4">
                  <div className="text-base font-semibold">{formatCurrency(getVariantPrice())}</div>
                  <div className={cn('text-sm', getVariantStock() === 0 ? 'text-destructive' : 'text-muted-foreground')}>
                    {getVariantStock()} {product.unit || 'pcs'}
                  </div>
                </div>
              )}

              {!selectedVariant && product.has_variants && variants.length > 0 && (
                <div className="py-4 text-center text-sm italic text-muted-foreground">
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

              <div className="mt-4">
                <label className="mb-2 block text-sm font-semibold">
                  Quantity
                  {getVariantStock() > 0 && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      (1 - {getVariantStock()})
                    </span>
                  )}
                </label>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-9 w-9 shrink-0"
                      onClick={() => {
                        const newQty = Math.max(1, quantity - 1);
                        setQuantity(newQty);
                        setQuantityInput(newQty.toString());
                        setQuantityError(null);
                      }}
                    >
                      -
                    </Button>
                    <Input
                      type="number"
                      min="1"
                      max={getVariantStock() > 0 ? getVariantStock() : undefined}
                      value={quantityInput}
                      onChange={(e) => {
                        setQuantityInput(e.target.value);
                        setQuantityError(null);
                      }}
                      onFocus={(e) => {
                        e.target.select();
                        setQuantityInput(quantity.toString());
                        setQuantityError(null);
                      }}
                      onBlur={(e) => {
                        validateAndSetQuantity(e.target.value.trim());
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.target.blur();
                        }
                        if (e.key === 'Escape') {
                          setQuantityInput(quantity.toString());
                          setQuantityError(null);
                          e.target.blur();
                        }
                      }}
                      className={cn(
                        'h-9 w-28 text-center text-base font-bold tabular-nums',
                        quantityError && 'border-destructive bg-destructive/5 text-destructive'
                      )}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-9 w-9 shrink-0"
                      onClick={() => {
                        const maxStock = getVariantStock();
                        const newQty = maxStock > 0 ? Math.min(quantity + 1, maxStock) : quantity + 1;
                        setQuantity(newQty);
                        setQuantityInput(newQty.toString());
                        setQuantityError(null);
                      }}
                      disabled={getVariantStock() > 0 && quantity >= getVariantStock()}
                    >
                      +
                    </Button>
                  </div>
                  {quantityError && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                      {quantityError}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="flex gap-3 border-t px-6 py-4">
          <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            className="flex-1"
            onClick={handleAddToCart}
            disabled={!canAddToCart() || getVariantStock() === 0}
          >
            Add to Cart
          </Button>
        </div>
      </div>
    </div>
  );
};

export default VariantSelector;

