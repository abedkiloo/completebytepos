import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pencil, ClipboardList } from 'lucide-react';

import { productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { catalogSellableStock } from '../../utils/catalogStock';
import { resolveMediaUrl } from '../../utils/mediaUrl';
import { variantDisplayLabel } from '../../utils/variantCombinations';
import {
  SELLING_PRICE_CLASS,
  VARIANT_PARENT_PRICE_MASK,
  STOCK_ON_HAND_LABEL,
  STOCK_COUNT_HINT,
} from '../../utils/productDisplay';
import { resolveProductDetailVisibility } from '../../utils/productAccess';
import { proposedPendingCost } from '../../utils/makerChecker';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import StockHistoryModal from '../Inventory/StockHistoryModal';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Skeleton } from '../ui/skeleton';
import { cn } from '../../lib/cn';

function DetailRow({ label, children }) {
  if (children == null || children === '') return null;
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <dt className="shrink-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm text-foreground sm:text-right">{children}</dd>
    </div>
  );
}

export default function ProductDetailPanel({
  productId,
  variantId = null,
  onClose,
  onEdit,
  onSetStock,
  fieldAccess,
  productModuleSettings = {},
  storeSettings = {},
  canViewStockHistory = false,
  showMovementCost = true,
}) {
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('details');
  const [focusedVariantId, setFocusedVariantId] = useState(variantId);

  const visibility = useMemo(
    () => resolveProductDetailVisibility(fieldAccess, productModuleSettings, storeSettings),
    [fieldAccess, productModuleSettings, storeSettings]
  );

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError('');
    try {
      const res = await productsAPI.get(productId);
      setProduct(res.data);
    } catch {
      setError('Could not load product details.');
      setProduct(null);
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setFocusedVariantId(variantId);
  }, [variantId, productId]);

  useEffect(() => {
    if (!canViewStockHistory && tab === 'history') {
      setTab('details');
    }
  }, [canViewStockHistory, tab]);

  const variants = product?.variants || [];
  const focusedVariant = useMemo(() => {
    if (!focusedVariantId) return null;
    return variants.find((v) => String(v.id) === String(focusedVariantId)) || null;
  }, [variants, focusedVariantId]);

  const imageSrc = product ? resolveMediaUrl(product.image_url || product.image) : null;
  const sellingPrice = parseFloat(product?.selling_price ?? product?.price ?? 0);
  const pricePending = visibility.catalogOnly && sellingPrice <= 0;
  const pendingCost = proposedPendingCost(product?.pending_approval);

  const showVariantFinancialCols =
    visibility.showPricing || visibility.showCost || visibility.showStock;

  const panelWide = canViewStockHistory && tab === 'history';
  const viewingVariant = Boolean(focusedVariant);

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div
        className={cn('slide-in-panel', panelWide ? 'max-w-3xl' : 'max-w-lg')}
        onClick={(e) => e.stopPropagation()}
        data-testid="product-detail-panel"
      >
        <div className="slide-in-panel-header">
          <h2>{viewingVariant ? 'Variant details' : 'Product details'}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        {canViewStockHistory && product && !loading && !error ? (
          <div
            className="flex gap-1 border-b px-4 pt-1"
            role="tablist"
            data-testid="product-detail-tabs"
          >
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'details'}
              className={cn(
                'px-3 py-2 text-sm font-medium border-b-2 -mb-px',
                tab === 'details'
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground'
              )}
              onClick={() => setTab('details')}
            >
              Details
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'history'}
              data-testid="product-stock-history-tab"
              className={cn(
                'px-3 py-2 text-sm font-medium border-b-2 -mb-px',
                tab === 'history'
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground'
              )}
              onClick={() => setTab('history')}
            >
              Stock history
            </button>
          </div>
        ) : null}

        <div className="slide-in-panel-body space-y-5">
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : product && tab === 'history' && canViewStockHistory ? (
            <StockHistoryModal
              product={product}
              embedded
              showCost={showMovementCost}
              onClose={onClose}
            />
          ) : product ? (
            <>
              <div className="flex gap-4">
                {imageSrc ? (
                  <img
                    src={imageSrc}
                    alt={product.name}
                    className="h-20 w-20 shrink-0 rounded-md border object-cover"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <h3 className="text-lg font-semibold leading-tight">{product.name}</h3>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {product.sku ? (
                      <span className="font-mono text-xs text-muted-foreground">{product.sku}</span>
                    ) : null}
                    {visibility.showStatus ? (
                      <Badge variant={product.is_active ? 'success' : 'outline'}>
                        {product.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    ) : null}
                    {product.has_variants ? (
                      <Badge variant="secondary">Has variants</Badge>
                    ) : null}
                    {visibility.showStock && product.is_low_stock ? (
                      <Badge variant="warning">Low stock</Badge>
                    ) : null}
                    {visibility.showStock && product.needs_reorder ? (
                      <Badge variant="outline">Needs reorder</Badge>
                    ) : null}
                    <PendingApprovalBadges pendingApproval={product.pending_approval} />
                  </div>
                </div>
              </div>

              {focusedVariant ? (
                <div
                  className="space-y-3 rounded-md border border-primary/30 bg-primary/5 p-3"
                  data-testid="focused-variant-detail"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Selected variant
                      </p>
                      <h4 className="text-base font-semibold">
                        {variantDisplayLabel(focusedVariant)}
                      </h4>
                      {focusedVariant.sku ? (
                        <p className="font-mono text-xs text-muted-foreground">
                          {focusedVariant.sku}
                        </p>
                      ) : null}
                    </div>
                    {visibility.showStatus ? (
                      <Badge variant={focusedVariant.is_active ? 'success' : 'outline'}>
                        {focusedVariant.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    ) : null}
                  </div>
                  <dl className="grid gap-2 sm:grid-cols-2">
                    {visibility.showStock ? (
                      <DetailRow label={STOCK_ON_HAND_LABEL}>
                        <span className="tabular-nums font-semibold">
                          {focusedVariant.stock_quantity ?? 0}
                        </span>
                        {focusedVariant.is_low_stock ? (
                          <Badge variant="warning" className="ml-1 px-1 py-0 text-[10px]">
                            Low
                          </Badge>
                        ) : null}
                      </DetailRow>
                    ) : null}
                    {visibility.showMrp ? (
                      <DetailRow label="MRP">
                        {formatCurrency(focusedVariant.mrp ?? focusedVariant.price)}
                      </DetailRow>
                    ) : null}
                    {visibility.showPricing ? (
                      <DetailRow label="Selling">
                        <span className={SELLING_PRICE_CLASS}>
                          {formatCurrency(
                            focusedVariant.price ?? focusedVariant.selling_price
                          )}
                        </span>
                      </DetailRow>
                    ) : null}
                    {visibility.showCost ? (
                      <DetailRow label="Cost">
                        {formatCurrency(
                          focusedVariant.cost ??
                            focusedVariant.effective_cost ??
                            product.cost
                        )}
                      </DetailRow>
                    ) : null}
                    {focusedVariant.barcode ? (
                      <DetailRow label="Barcode">{focusedVariant.barcode}</DetailRow>
                    ) : null}
                  </dl>
                  {variants.length > 1 ? (
                    <button
                      type="button"
                      className="text-xs text-primary underline-offset-2 hover:underline"
                      onClick={() => setFocusedVariantId(null)}
                    >
                      Show all variants
                    </button>
                  ) : null}
                </div>
              ) : null}

              <dl className="space-y-3 rounded-md border border-border/60 bg-muted/20 p-3">
                <DetailRow label="Category">
                  {product.category_name || product.category_detail?.name || '—'}
                  {product.subcategory_name || product.subcategory_detail?.name
                    ? ` → ${product.subcategory_name || product.subcategory_detail?.name}`
                    : ''}
                </DetailRow>
                <DetailRow label="Barcode">{product.barcode}</DetailRow>
                <DetailRow label="Unit">{product.unit}</DetailRow>

                {visibility.catalogOnly ? (
                  <DetailRow label="Price">
                    {product.has_variants ? (
                      <span className="text-muted-foreground">{VARIANT_PARENT_PRICE_MASK}</span>
                    ) : pricePending ? (
                      <Badge variant="outline" className="font-normal">
                        Pending manager
                      </Badge>
                    ) : (
                      <span className={SELLING_PRICE_CLASS}>{formatCurrency(sellingPrice)}</span>
                    )}
                  </DetailRow>
                ) : null}

                {!visibility.catalogOnly && !product.has_variants && visibility.showPricing ? (
                  <>
                    {visibility.showMrp ? (
                      <DetailRow label="MRP">
                        {formatCurrency(product.mrp ?? product.price)}
                      </DetailRow>
                    ) : null}
                    <DetailRow label="Selling price">
                      <span className={SELLING_PRICE_CLASS}>
                        {formatCurrency(product.selling_price ?? product.price)}
                      </span>
                    </DetailRow>
                  </>
                ) : null}

                {!visibility.catalogOnly && visibility.showCost && !product.has_variants ? (
                  <DetailRow label="Cost">
                    <span className="inline-flex flex-col items-end gap-1">
                      <span>{formatCurrency(product.cost)}</span>
                      {pendingCost != null ? (
                        <span className="text-xs text-amber-700">
                          Pending: {formatCurrency(pendingCost)}
                        </span>
                      ) : null}
                    </span>
                  </DetailRow>
                ) : null}

                {!visibility.catalogOnly && visibility.showProfit && !product.has_variants ? (
                  <>
                    <DetailRow label="Profit margin">
                      {product.profit_margin != null ? `${product.profit_margin}%` : '—'}
                    </DetailRow>
                    <DetailRow label="Profit per unit">
                      {formatCurrency(product.profit_amount)}
                    </DetailRow>
                    <DetailRow label="Stock value">
                      {formatCurrency(product.total_value)}
                    </DetailRow>
                  </>
                ) : null}

                {!visibility.catalogOnly && visibility.showStock ? (
                  <>
                    <DetailRow label={STOCK_ON_HAND_LABEL}>
                      {product.track_stock
                        ? product.has_variants
                          ? catalogSellableStock(product)
                          : product.stock_quantity ?? 0
                        : 'Not tracked'}
                    </DetailRow>
                    {product.track_stock ? (
                      <p className="text-xs text-muted-foreground">
                        {STOCK_COUNT_HINT}
                      </p>
                    ) : null}
                    <DetailRow label="Track stock">
                      {product.track_stock ? 'Yes' : 'No'}
                    </DetailRow>
                    {product.track_stock ? (
                      <>
                        <DetailRow label="Low stock at">
                          {product.low_stock_threshold ?? '—'}
                        </DetailRow>
                        <DetailRow label="Reorder quantity">
                          {product.reorder_quantity ?? '—'}
                        </DetailRow>
                      </>
                    ) : null}
                  </>
                ) : null}

                {!visibility.catalogOnly && visibility.showPricing ? (
                  <>
                    <DetailRow label="Tax rate">
                      {product.is_taxable
                        ? `${product.tax_rate ?? 0}%`
                        : 'Not taxable'}
                    </DetailRow>
                  </>
                ) : null}

                {product.supplier_name_display || product.supplier_name ? (
                  <DetailRow label="Supplier">
                    {product.supplier_name_display || product.supplier_name}
                  </DetailRow>
                ) : null}
                {product.description ? (
                  <DetailRow label="Description">
                    <span className="whitespace-pre-wrap text-left sm:text-right">
                      {product.description}
                    </span>
                  </DetailRow>
                ) : null}
              </dl>

              {product.has_variants &&
              variants.length > 0 &&
              visibility.catalogOnly &&
              !showVariantFinancialCols ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Variants</h4>
                  <ul className="space-y-1 rounded-md border px-3 py-2 text-sm">
                    {variants.map((variant) => (
                      <li key={variant.id}>
                        <button
                          type="button"
                          className="flex w-full flex-wrap items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-muted/60"
                          onClick={() => setFocusedVariantId(variant.id)}
                        >
                          <span>{variantDisplayLabel(variant)}</span>
                          {variant.sku ? (
                            <span className="font-mono text-[11px] text-muted-foreground">
                              {variant.sku}
                            </span>
                          ) : null}
                          {visibility.showStock ? (
                            <span className="ml-auto tabular-nums text-xs text-muted-foreground">
                              Stock {variant.stock_quantity ?? 0}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {product.has_variants && variants.length > 0 && showVariantFinancialCols ? (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Variants</h4>
                  <div className="overflow-x-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
                        <tr>
                          <th className="px-3 py-2 font-medium">Size / color</th>
                          {visibility.showMrp ? (
                            <th className="px-3 py-2 text-right font-medium">MRP</th>
                          ) : null}
                          {visibility.showPricing ? (
                            <th className="px-3 py-2 text-right font-medium">Price</th>
                          ) : null}
                          {visibility.showCost ? (
                            <th className="px-3 py-2 text-right font-medium">Cost</th>
                          ) : null}
                          {visibility.showStock ? (
                            <th className="px-3 py-2 text-right font-medium">Stock</th>
                          ) : null}
                          {visibility.showStatus ? (
                            <th className="px-3 py-2 font-medium">Status</th>
                          ) : null}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {variants.map((variant) => {
                          const isFocused =
                            focusedVariantId != null &&
                            String(variant.id) === String(focusedVariantId);
                          return (
                          <tr
                            key={variant.id}
                            className={cn(
                              'cursor-pointer transition-colors hover:bg-muted/50',
                              isFocused && 'bg-primary/10'
                            )}
                            onClick={() => setFocusedVariantId(variant.id)}
                            data-testid={
                              isFocused ? 'variant-row-focused' : `variant-row-${variant.id}`
                            }
                          >
                            <td className="px-3 py-2">
                              <div className="font-medium">{variantDisplayLabel(variant)}</div>
                              {variant.sku ? (
                                <div className="font-mono text-[11px] text-muted-foreground">
                                  {variant.sku}
                                </div>
                              ) : null}
                              {variant.barcode ? (
                                <div className="text-[11px] text-muted-foreground">
                                  {variant.barcode}
                                </div>
                              ) : null}
                              <PendingApprovalBadges
                                pendingApproval={variant.pending_approval}
                                className="mt-1"
                              />
                            </td>
                            {visibility.showMrp ? (
                              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                                {formatCurrency(variant.mrp ?? variant.price)}
                              </td>
                            ) : null}
                            {visibility.showPricing ? (
                              <td
                                className={`px-3 py-2 text-right tabular-nums ${SELLING_PRICE_CLASS}`}
                              >
                                {formatCurrency(variant.price ?? variant.selling_price)}
                              </td>
                            ) : null}
                            {visibility.showCost ? (
                              <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                                {formatCurrency(
                                  variant.cost ?? variant.effective_cost ?? product.cost
                                )}
                              </td>
                            ) : null}
                            {visibility.showStock ? (
                              <td className="px-3 py-2 text-right tabular-nums font-semibold">
                                {variant.stock_quantity ?? 0}
                                {variant.is_low_stock ? (
                                  <Badge variant="warning" className="ml-1 px-1 py-0 text-[10px]">
                                    Low
                                  </Badge>
                                ) : null}
                              </td>
                            ) : null}
                            {visibility.showStatus ? (
                              <td className="px-3 py-2">
                                <Badge variant={variant.is_active ? 'success' : 'outline'}>
                                  {variant.is_active ? 'Active' : 'Inactive'}
                                </Badge>
                              </td>
                            ) : null}
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              {product.has_variants && (
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {(product.available_sizes_detail || []).map((s) => (
                    <Badge key={`s-${s.id}`} variant="outline">
                      Size: {s.name}
                    </Badge>
                  ))}
                  {(product.available_colors_detail || []).map((c) => (
                    <Badge key={`c-${c.id}`} variant="outline">
                      Color: {c.name}
                    </Badge>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>

        {product && tab === 'details' && (onEdit || onSetStock) ? (
          <div className="slide-in-panel-footer">
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
            {onSetStock && visibility.showStock && product.track_stock ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => onSetStock(product, focusedVariant || null)}
              >
                <ClipboardList className="mr-2 h-4 w-4" />
                Set {STOCK_ON_HAND_LABEL.toLowerCase()}
                {focusedVariant ? ` · ${variantDisplayLabel(focusedVariant)}` : ''}
              </Button>
            ) : null}
            {onEdit && visibility.canEdit ? (
              <Button type="button" onClick={() => onEdit(product)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit product
              </Button>
            ) : null}
          </div>
        ) : (
          <div className="slide-in-panel-footer">
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
