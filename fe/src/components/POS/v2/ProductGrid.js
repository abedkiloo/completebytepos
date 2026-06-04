import React from 'react';
import { Search, Package, Filter } from 'lucide-react';

import { Input } from '../../ui/input';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { Skeleton } from '../../ui/skeleton';
import { Badge } from '../../ui/badge';
import { formatCurrency } from '../../../utils/formatters';
import { cn } from '../../../lib/cn';
import { isProductOutOfStock } from '../../../utils/productStock';
import { resolveMediaUrl } from '../../../utils/mediaUrl';
import PendingApprovalBadges from '../../Approvals/PendingApprovalBadges';

/**
 * Left + centre region of the POS:
 *   - search box (debounced upstream)
 *   - horizontal category tabs (top-level + subcategories)
 *   - product grid with stock chips
 *
 * Everything below the search row is independently scrollable so the search
 * stays pinned even when the catalogue is long. Buttons hit the 44 px touch
 * target via the `pos-target` utility on each tile.
 */
export function ProductGrid({
  products,
  categories,
  loading,
  searchQuery,
  onSearchChange,
  selectedCategory,
  selectedSubcategory,
  onSelectCategory,
  onSelectSubcategory,
  onAddToCart,
  searchInputRef,
  respectStockLimits = true,
}) {
  const activeTop = categories.find((c) => c.id === selectedCategory);
  const subcategories = activeTop?.children || [];

  return (
    <div className="flex h-full min-h-0 flex-col bg-secondary/30">
      {/* Search */}
      <div className="border-b bg-background px-4 py-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search products or scan a barcode…  (F2)"
            className="h-11 pl-10 text-base"
            autoComplete="off"
            inputMode="search"
          />
        </div>
      </div>

      {/* Top-level category tabs */}
      <div className="border-b bg-background">
        <ScrollArea className="w-full">
          <div className="flex gap-1 px-3 py-2">
            <CategoryChip
              active={selectedCategory === 'all'}
              onClick={() => {
                onSelectCategory('all');
                onSelectSubcategory(null);
              }}
              label="All"
              icon={Package}
            />
            {categories.map((cat) => (
              <CategoryChip
                key={cat.id}
                active={selectedCategory === cat.id}
                onClick={() => {
                  onSelectCategory(cat.id);
                  onSelectSubcategory(null);
                }}
                label={cat.name}
                badge={cat.children?.length}
              />
            ))}
          </div>
        </ScrollArea>

        {/* Sub-category row, only when a top-level category with children is active */}
        {subcategories.length > 0 && (
          <div className="border-t bg-secondary/40">
            <ScrollArea className="w-full">
              <div className="flex gap-1 px-3 py-2">
                <CategoryChip
                  active={!selectedSubcategory}
                  onClick={() => onSelectSubcategory(null)}
                  label={`All ${activeTop.name}`}
                  size="sm"
                />
                {subcategories.map((sub) => (
                  <CategoryChip
                    key={sub.id}
                    active={selectedSubcategory === sub.id}
                    onClick={() => onSelectSubcategory(sub.id)}
                    label={sub.name}
                    size="sm"
                  />
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      {/* Product grid */}
      <div className="min-h-0 flex-1">
        <ScrollArea className="h-full">
          <div className="p-4">
            {loading ? (
              <ProductGridSkeleton />
            ) : products.length === 0 ? (
              <EmptyState searchQuery={searchQuery} />
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
                {products.map((product) => (
                  <ProductTile
                    key={product.id}
                    product={product}
                    respectStockLimits={respectStockLimits}
                    onClick={() => onAddToCart(product)}
                  />
                ))}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function CategoryChip({ active, onClick, label, badge, icon: Icon, size = 'md' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'pos-target inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 text-sm font-medium transition-colors',
        size === 'sm' ? 'h-8 px-3 text-xs' : 'h-10 px-4',
        active
          ? 'border-primary bg-primary text-primary-foreground shadow-sm'
          : 'border-border bg-background text-foreground hover:bg-accent'
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5" />}
      <span>{label}</span>
      {!!badge && (
        <Badge variant={active ? 'secondary' : 'outline'} className="h-5 px-1.5 text-[10px]">
          {badge}
        </Badge>
      )}
    </button>
  );
}

function ProductTile({ product, onClick, respectStockLimits = true }) {
  const stock = product.stock_quantity ?? 0;
  const lowStock = product.track_stock && stock > 0 && stock <= (product.low_stock_threshold || 5);
  const outOfStock = respectStockLimits && isProductOutOfStock(product);

  return (
    <button
      type="button"
      onClick={outOfStock ? undefined : onClick}
      disabled={outOfStock}
      aria-disabled={outOfStock}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-lg border bg-card text-left shadow-sm transition-all',
        outOfStock
          ? 'cursor-not-allowed border-red-300 bg-red-50/80 opacity-90'
          : 'hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md',
        'focus-visible:-translate-y-0.5 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        outOfStock && 'hover:translate-y-0 hover:shadow-sm'
      )}
    >
      {/* Image placeholder area */}
      <div className="relative flex aspect-square w-full items-center justify-center bg-muted">
        {product.image_url || product.image ? (
          <img
            src={resolveMediaUrl(product.image_url || product.image)}
            alt={product.name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <Package className="h-10 w-10 text-muted-foreground/40" />
        )}
        {outOfStock && (
          <Badge variant="destructive" className="absolute right-2 top-2">
            Out of stock
          </Badge>
        )}
        {!outOfStock && lowStock && (
          <Badge variant="warning" className="absolute right-2 top-2">
            Low: {stock}
          </Badge>
        )}
      </div>

      {/* Meta */}
      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <div className="flex flex-wrap items-start gap-1">
          <PendingApprovalBadges
            pendingApproval={product.pending_approval}
            className="mb-0.5"
          />
        </div>
        <span
          className={cn(
            'line-clamp-2 text-sm font-medium leading-tight',
            outOfStock ? 'text-red-700' : 'text-foreground'
          )}
        >
          {product.name}
        </span>
        <span className="mt-auto text-base font-semibold text-foreground">
          {formatCurrency(product.price)}
        </span>
      </div>
    </button>
  );
}

function ProductGridSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="overflow-hidden rounded-lg border bg-card shadow-sm">
          <Skeleton className="aspect-square w-full rounded-none" />
          <div className="flex flex-col gap-2 p-2.5">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="mt-1 h-5 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ searchQuery }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed bg-background/50 px-6 text-center">
      <Filter className="h-10 w-10 text-muted-foreground" />
      <div>
        <p className="font-medium text-foreground">No products match</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {searchQuery
            ? `Nothing for "${searchQuery}". Try a different name or category.`
            : 'No products in this category yet. Add some from the Products screen.'}
        </p>
      </div>
    </div>
  );
}
