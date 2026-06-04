import React, { useState, useEffect } from 'react';
import { variantsAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  findVariantForSelection,
  getSellableStockForVariant,
  getVariantDisplayPrice,
  canAddVariantToCart,
  isVariantAddToCartDisabled,
  buildVariantCartPayload,
} from '../../utils/variantSelector';

const VariantSelector = ({ product, onSelect, onClose, validateStock = true }) => {
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

  useEffect(() => {
    setQuantityInput(quantity.toString());
    setQuantityError(null);
  }, [quantity]);

  const loadProductDetails = async () => {
    setLoadingDetails(true);
    try {
      const response = await productsAPI.get(product.id);
      const fullProduct = response.data;

      const sizes =
        fullProduct.available_sizes_detail ||
        fullProduct.available_sizes ||
        product.available_sizes_detail ||
        product.available_sizes ||
        [];
      const colors =
        fullProduct.available_colors_detail ||
        fullProduct.available_colors ||
        product.available_colors_detail ||
        product.available_colors ||
        [];

      setAvailableSizes(Array.isArray(sizes) ? sizes : []);
      setAvailableColors(Array.isArray(colors) ? colors : []);
    } catch (error) {
      console.error('[VariantSelector] Error loading product details:', error);
      if (product.available_sizes_detail?.length) {
        setAvailableSizes(product.available_sizes_detail);
      } else if (product.available_sizes?.length) {
        setAvailableSizes(product.available_sizes);
      }
      if (product.available_colors_detail?.length) {
        setAvailableColors(product.available_colors_detail);
      } else if (product.available_colors?.length) {
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
    } catch (error) {
      console.error('Error loading variants:', error);
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

  useEffect(() => {
    const variant = findVariantForSelection(
      variants,
      selectedSize,
      selectedColor,
      availableSizes,
      availableColors
    );
    setSelectedVariant(variant);
  }, [selectedSize, selectedColor, variants, availableSizes, availableColors]);

  const effectiveStock = getSellableStockForVariant(
    product,
    selectedVariant,
    variants
  );
  const canAdd = canAddVariantToCart({
    product,
    variants,
    selectedSize,
    selectedColor,
    selectedVariant,
    availableSizes,
    availableColors,
  });
  const addDisabled = isVariantAddToCartDisabled({
    product,
    selectedVariant,
    canAdd,
    validateStock,
    variantsList: variants,
  });

  const handleAddToCart = () => {
    if (addDisabled) return;
    const payload = buildVariantCartPayload(
      product,
      selectedVariant,
      quantity,
      variants
    );
    onSelect(payload);
  };

  const getVariantStock = () => {
    if (effectiveStock === null) return null;
    return effectiveStock;
  };

  const getVariantPrice = () => getVariantDisplayPrice(product, selectedVariant);

  const validateAndSetQuantity = (inputValue) => {
    setQuantityError(null);

    if (inputValue === '' || inputValue === '-' || inputValue == null) {
      setQuantity(1);
      setQuantityInput('1');
      return;
    }

    const numValue = parseInt(inputValue, 10);

    if (Number.isNaN(numValue)) {
      setQuantityError('Please enter a valid number');
      setQuantity(1);
      setQuantityInput('1');
      return;
    }

    const maxStock = getVariantStock();
    const minValue = 1;

    if (numValue < minValue) {
      setQuantityError(`Minimum quantity is ${minValue}`);
      const finalVal = minValue;
      setQuantity(finalVal);
      setQuantityInput(finalVal.toString());
      return;
    }

    if (validateStock && maxStock != null && maxStock > 0 && numValue > maxStock) {
      setQuantityError(`Maximum quantity is ${maxStock} (stock available)`);
      const finalVal = maxStock;
      setQuantity(finalVal);
      setQuantityInput(finalVal.toString());
      return;
    }

    setQuantity(numValue);
    setQuantityInput(numValue.toString());
  };

  if (!product.has_variants && variants.length === 0) {
    onSelect(buildVariantCartPayload(product, null, 1));
    return null;
  }

  const stockDisplay = getVariantStock();
  const showSelectionSummary = selectedVariant != null;

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

              {showSelectionSummary && (
                <div className="mt-4 rounded-md bg-muted/40 p-4">
                  <div className="text-base font-semibold">{formatCurrency(getVariantPrice())}</div>
                  <div
                    className={cn(
                      'text-sm',
                      validateStock && stockDisplay === 0
                        ? 'text-destructive'
                        : 'text-muted-foreground'
                    )}
                  >
                    {stockDisplay === null
                      ? 'Stock not tracked'
                      : `${stockDisplay} ${product.unit || 'pcs'}`}
                  </div>
                  {validateStock && stockDisplay === 0 && (
                    <p className="mt-2 text-xs text-destructive">
                      No stock on this variant. Adjust inventory or turn off stock validation in Sales settings.
                    </p>
                  )}
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
                  {validateStock && stockDisplay != null && stockDisplay > 0 && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      (1 - {stockDisplay})
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
                      max={
                        validateStock && stockDisplay != null && stockDisplay > 0
                          ? stockDisplay
                          : undefined
                      }
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
                        const newQty =
                          validateStock && maxStock != null && maxStock > 0
                            ? Math.min(quantity + 1, maxStock)
                            : quantity + 1;
                        setQuantity(newQty);
                        setQuantityInput(newQty.toString());
                        setQuantityError(null);
                      }}
                      disabled={
                        validateStock &&
                        stockDisplay != null &&
                        stockDisplay > 0 &&
                        quantity >= stockDisplay
                      }
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
            disabled={addDisabled}
          >
            Add to Cart
          </Button>
        </div>
      </div>
    </div>
  );
};

export default VariantSelector;
