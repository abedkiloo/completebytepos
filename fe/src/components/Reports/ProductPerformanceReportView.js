import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PackageSearch } from 'lucide-react';

import { productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { EmptyState, FilterBar, FilterField, PageLoading } from '../page';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import ProductTrendsPanel from '../Products/ProductTrendsPanel';

const SEARCH_LIMIT = 12;
const SEARCH_DEBOUNCE_MS = 280;

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

/**
 * Reports desk: pick any catalogue product and study month/quarter performance.
 *
 * Reuses ``ProductTrendsPanel`` (same charts as the product detail Performance tab).
 * Gated upstream by product reports + ``reports.product_trends``.
 */
export default function ProductPerformanceReportView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlProductId = searchParams.get('product_id');

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [loadingSelected, setLoadingSelected] = useState(Boolean(urlProductId));
  const [focusedVariantId, setFocusedVariantId] = useState(null);

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

  const pickProduct = useCallback(
    (product) => {
      if (!product?.id) return;
      setSelected(product);
      setFocusedVariantId(null);
      setQuery('');
      setResults([]);
      const next = new URLSearchParams(searchParams);
      next.set('report', 'product-performance');
      next.set('product_id', String(product.id));
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const clearProduct = useCallback(() => {
    setSelected(null);
    setFocusedVariantId(null);
    const next = new URLSearchParams(searchParams);
    next.set('report', 'product-performance');
    next.delete('product_id');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const variants = useMemo(() => {
    if (!selected) return [];
    if (Array.isArray(selected.variants)) return selected.variants;
    return [];
  }, [selected]);

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
            placeholder="Search by name or SKU…"
            aria-label="Search products for performance"
            data-testid="product-performance-search"
            autoComplete="off"
          />
        </FilterField>
        {selected ? (
          <div className="flex flex-wrap items-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={clearProduct}
              data-testid="product-performance-clear"
            >
              Clear selection
            </Button>
          </div>
        ) : null}
      </FilterBar>

      {query.trim() && !selected ? (
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
                    <span className="font-medium text-foreground">{productOptionLabel(row)}</span>
                    <span className="text-xs text-muted-foreground">Open</span>
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
          description="Search any catalogue item to see sold units, revenue, and stock received by month or quarter."
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
            </p>
          </div>
          <ProductTrendsPanel
            productId={selected.id}
            variantId={focusedVariantId}
            variants={variants}
            onVariantChange={(nextId) => setFocusedVariantId(nextId)}
          />
        </div>
      )}
    </div>
  );
}
