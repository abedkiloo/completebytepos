import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PackageSearch, X } from 'lucide-react';

import { productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { EmptyState, FilterBar, FilterField, PageLoading } from '../page';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import ProductTrendsPanel from '../Products/ProductTrendsPanel';

const SEARCH_LIMIT = 12;
const SEARCH_DEBOUNCE_MS = 280;
const MAX_COMPARE = 4;

/**
 * Normalise a product list API payload into a flat array.
 *
 * @param {unknown} payload Axios `data` from products list/search.
 * @returns {Array<object>} Zero or more product rows.
 */
export function normalizeProductSearchResults(payload) {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.results)) return payload.results;
  return [];
}

/**
 * Label for a product option in the performance report picker.
 *
 * @param {object|null|undefined} product Product row with name/sku.
 * @returns {string} Display label, at most ~120 characters.
 */
export function productOptionLabel(product) {
  if (!product || typeof product !== 'object') return 'Product';
  const name = String(product.name || '').trim() || `Product #${product.id || '?'}`;
  const sku = String(product.sku || '').trim();
  return sku ? `${name} · ${sku}` : name;
}

function parseIdList(raw) {
  if (!raw) return [];
  return String(raw)
    .split(',')
    .map((part) => Number(part.trim()))
    .filter((id) => Number.isFinite(id) && id > 0);
}

/**
 * Reports desk: pick a primary product, optional peers, and study trends.
 *
 * Reuses ``ProductTrendsPanel``. Supports multi-product compare and custom
 * end month/quarter inside the panel. Gated upstream by product reports +
 * ``reports.product_trends``.
 */
export default function ProductPerformanceReportView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlProductId = searchParams.get('product_id');
  const urlCompare = searchParams.get('compare_ids') || '';

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [compareProducts, setCompareProducts] = useState([]);
  const [loadingSelected, setLoadingSelected] = useState(Boolean(urlProductId));
  const [focusedVariantId, setFocusedVariantId] = useState(null);
  const [pickMode, setPickMode] = useState('primary'); // primary | compare

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    if (!debouncedQuery) {
      setResults([]);
      setSearching(false);
      return undefined;
    }
    setSearching(true);
    productsAPI
      .list({
        search: debouncedQuery,
        is_active: 'true',
        page_size: SEARCH_LIMIT,
      })
      .then((res) => {
        if (cancelled) return;
        setResults(normalizeProductSearchResults(res.data).slice(0, SEARCH_LIMIT));
      })
      .catch(() => {
        if (cancelled) return;
        setResults([]);
        toast.error('Could not search products');
      })
      .finally(() => {
        if (!cancelled) setSearching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  useEffect(() => {
    let cancelled = false;
    const id = urlProductId ? Number(urlProductId) : 0;
    if (!id || !Number.isFinite(id) || id <= 0) {
      setLoadingSelected(false);
      return undefined;
    }
    setLoadingSelected(true);
    productsAPI
      .get(id)
      .then((res) => {
        if (cancelled) return;
        setSelected(res.data || null);
        setFocusedVariantId(null);
      })
      .catch(() => {
        if (cancelled) return;
        setSelected(null);
        toast.error('Could not load that product');
      })
      .finally(() => {
        if (!cancelled) setLoadingSelected(false);
      });
    return () => {
      cancelled = true;
    };
  }, [urlProductId]);

  useEffect(() => {
    let cancelled = false;
    const ids = parseIdList(urlCompare).filter(
      (id) => id !== Number(urlProductId)
    );
    if (!ids.length) {
      setCompareProducts([]);
      return undefined;
    }
    Promise.all(ids.map((id) => productsAPI.get(id).then((r) => r.data).catch(() => null)))
      .then((rows) => {
        if (cancelled) return;
        setCompareProducts(rows.filter(Boolean).slice(0, MAX_COMPARE));
      });
    return () => {
      cancelled = true;
    };
  }, [urlCompare, urlProductId]);

  const writeUrl = useCallback(
    (primaryId, peers) => {
      const next = new URLSearchParams(searchParams);
      next.set('report', 'product-performance');
      if (primaryId) next.set('product_id', String(primaryId));
      else next.delete('product_id');
      const peerIds = (peers || [])
        .map((p) => p.id)
        .filter((id) => id && id !== primaryId)
        .slice(0, MAX_COMPARE);
      if (peerIds.length) next.set('compare_ids', peerIds.join(','));
      else next.delete('compare_ids');
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const pickProduct = useCallback(
    (product) => {
      if (!product?.id) return;
      if (pickMode === 'compare' && selected) {
        if (Number(product.id) === Number(selected.id)) {
          toast.error('That product is already the primary selection.');
          return;
        }
        if (compareProducts.some((p) => Number(p.id) === Number(product.id))) {
          toast.error('Already in the compare list.');
          return;
        }
        if (compareProducts.length >= MAX_COMPARE) {
          toast.error(`Compare up to ${MAX_COMPARE} other products.`);
          return;
        }
        const peers = [...compareProducts, product].slice(0, MAX_COMPARE);
        setCompareProducts(peers);
        setQuery('');
        setResults([]);
        writeUrl(selected.id, peers);
        return;
      }
      setSelected(product);
      setFocusedVariantId(null);
      setQuery('');
      setResults([]);
      setPickMode('primary');
      writeUrl(product.id, compareProducts);
    },
    [pickMode, selected, compareProducts, writeUrl]
  );

  const removeCompare = useCallback(
    (productId) => {
      const peers = compareProducts.filter((p) => Number(p.id) !== Number(productId));
      setCompareProducts(peers);
      if (selected?.id) writeUrl(selected.id, peers);
    },
    [compareProducts, selected, writeUrl]
  );

  const clearProduct = useCallback(() => {
    setSelected(null);
    setCompareProducts([]);
    setFocusedVariantId(null);
    setPickMode('primary');
    writeUrl(null, []);
  }, [writeUrl]);

  const variants = useMemo(() => {
    if (!selected) return [];
    if (Array.isArray(selected.variants)) return selected.variants;
    return [];
  }, [selected]);

  const compareIds = useMemo(
    () => compareProducts.map((p) => p.id),
    [compareProducts]
  );

  return (
    <div
      className="product-performance-report space-y-6"
      data-testid="product-performance-report"
    >
      <FilterBar className="print:hidden">
        <FilterField label="Find a product" className="sm:col-span-2">
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              pickMode === 'compare'
                ? 'Add another product to compare…'
                : 'Search by name or SKU…'
            }
            aria-label="Search products for performance"
            data-testid="product-performance-search"
            autoComplete="off"
          />
        </FilterField>
        <div className="flex flex-wrap items-end gap-2">
          {selected ? (
            <>
              <Button
                type="button"
                variant={pickMode === 'compare' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setPickMode('compare')}
                data-testid="product-performance-add-compare"
                disabled={compareProducts.length >= MAX_COMPARE}
              >
                Add to compare
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={clearProduct}
                data-testid="product-performance-clear"
              >
                Clear selection
              </Button>
            </>
          ) : null}
        </div>
      </FilterBar>

      {selected || compareProducts.length ? (
        <div
          className="flex flex-wrap items-center gap-2"
          data-testid="product-performance-compare-chips"
        >
          {selected ? (
            <Badge
              variant="secondary"
              className="gap-1 px-2 py-1 text-xs"
              data-testid="product-performance-primary-chip"
            >
              Primary · {productOptionLabel(selected)}
            </Badge>
          ) : null}
          {compareProducts.map((p) => (
            <Badge
              key={p.id}
              variant="outline"
              className="gap-1 px-2 py-1 text-xs"
              data-testid={`product-performance-compare-chip-${p.id}`}
            >
              {productOptionLabel(p)}
              <button
                type="button"
                className="ml-1 rounded-sm hover:bg-muted"
                aria-label={`Remove ${productOptionLabel(p)} from compare`}
                onClick={() => removeCompare(p.id)}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}

      {query.trim() ? (
        <div
          className="rounded-md border border-border bg-background"
          data-testid="product-performance-results"
        >
          {searching ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">Searching…</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">No products match.</p>
          ) : (
            <ul className="divide-y divide-border">
              {results.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50"
                    onClick={() => pickProduct(row)}
                    data-testid={`product-performance-pick-${row.id}`}
                  >
                    <span className="font-medium text-foreground">
                      {productOptionLabel(row)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {pickMode === 'compare' && selected ? 'Compare' : 'Open'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {loadingSelected ? (
        <PageLoading rows={6} showStats />
      ) : !selected ? (
        <EmptyState
          icon={PackageSearch}
          title="Pick a product"
          description="Search a catalogue item, then add peers to compare. Choose any end month or quarter in the charts to plan the next purchase."
        />
      ) : (
        <div className="space-y-3">
          <div>
            <h2
              className="text-lg font-semibold text-foreground"
              data-testid="product-performance-selected-name"
            >
              {selected.name || productOptionLabel(selected)}
            </h2>
            <p className="text-sm text-muted-foreground">
              {[selected.sku, selected.category_name || selected.category?.name]
                .filter(Boolean)
                .join(' · ') || 'Catalogue product'}
              {compareIds.length
                ? ` · comparing with ${compareIds.length} other product${
                    compareIds.length === 1 ? '' : 's'
                  }`
                : ''}
            </p>
          </div>
          <ProductTrendsPanel
            productId={selected.id}
            variantId={focusedVariantId}
            variants={variants}
            onVariantChange={(nextId) => setFocusedVariantId(nextId)}
            compareProductIds={compareIds}
          />
        </div>
      )}
    </div>
  );
}
