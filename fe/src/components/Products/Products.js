import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Plus,
  Search,
  Filter,
  Pencil,
  Trash2,
  Package,
  AlertCircle,
  XCircle,
  Download,
  Upload,
  FileText,
  ImageIcon,
  X,
  Loader2,
  MoreHorizontal,
  Scale,
} from 'lucide-react';

import { productsAPI, categoriesAPI } from '../../services/api';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import { formatCurrency } from '../../utils/formatters';
import { resolveMediaUrl } from '../../utils/mediaUrl';
import ProductForm from './ProductForm';
import ProductDetailPanel from './ProductDetailPanel';
import StockAdjustmentModal from '../Inventory/StockAdjustmentModal';
import { inventoryAdjustmentsEnabled } from '../../utils/inventoryDisplay';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { cn } from '../../lib/cn';
import { PageShell, PageHeader } from '../page';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { getPersonaFromStorage } from '../../utils/navAccess';
import { PERSONA } from '../../utils/roleAccess';
import { resolveProductFieldAccess } from '../../utils/productAccess';
import {
  SELLING_PRICE_CLASS,
  showProductStatus,
  showProductCostPrice,
  showProductMrp,
  showProductSkuInList,
  showProductLowStockBadges,
  productBulkOperationsEnabled,
  productCsvImportExportEnabled,
} from '../../utils/productDisplay';

const EMPTY_FILTERS = {
  search: '',
  category: '',
  is_active: '',
  low_stock: false,
  out_of_stock: false,
};

const Products = () => {
  const { settings: storeSettings } = useStoreSettings();
  const { settings: productModuleSettings } = useModuleSettings('products');
  const { settings: inventoryModuleSettings } = useModuleSettings('inventory');
  const persona = getPersonaFromStorage();
  const fieldAccess = resolveProductFieldAccess(
    persona,
    productModuleSettings,
    storeSettings
  );
  const catalogOnly = fieldAccess.catalogOnly;
  const financialFieldsLocked =
    !fieldAccess.pricing && !fieldAccess.cost && !fieldAccess.stock;
  const canAdjustStock =
    !catalogOnly && inventoryAdjustmentsEnabled(inventoryModuleSettings);
  const showStatus = showProductStatus(productModuleSettings, storeSettings);
  const showCost = showProductCostPrice(productModuleSettings);
  const showMrp = showProductMrp(productModuleSettings);
  const showSku = showProductSkuInList(productModuleSettings);
  const showLowStock = showProductLowStockBadges(productModuleSettings);
  const bulkEnabled = productBulkOperationsEnabled(productModuleSettings);
  const csvEnabled = productCsvImportExportEnabled(productModuleSettings);
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);

  // --- Data ---
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);

  // --- Filters ---
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  // --- Editor + selection ---
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [selectedProductIds, setSelectedProductIds] = useState([]);

  // --- Confirms ---
  const [confirmDelete, setConfirmDelete] = useState(null); // product id
  const [deleteReason, setDeleteReason] = useState('');
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [adjustStockProduct, setAdjustStockProduct] = useState(null);
  const [viewProductId, setViewProductId] = useState(null);

  // --- CSV import file input ---
  const fileInputRef = useRef(null);

  // ------------------------------------------------------------------
  // Data loaders
  // ------------------------------------------------------------------

  const loadCategories = useCallback(async () => {
    try {
      const response = await categoriesAPI.list();
      const data = response.data.results || response.data || [];
      setCategories(Array.isArray(data) ? data : []);
    } catch (error) {
      // Categories are best-effort; the filter just won't have them.
      console.error('Error loading categories:', error);
    }
  }, []);

  const loadStatistics = useCallback(async () => {
    try {
      const response = await productsAPI.statistics();
      setStatistics(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  }, []);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page_size: 1000 };
      if (filters.search.trim()) params.search = filters.search.trim();
      if (filters.category) params.category = filters.category;
      if (showStatus && filters.is_active) params.is_active = filters.is_active;
      if (filters.low_stock) params.low_stock = 'true';
      if (filters.out_of_stock) params.out_of_stock = 'true';

      const response = await productsAPI.list(params);
      const data = response.data.results || response.data || [];
      setProducts(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error loading products:', error);
      toast.error('Failed to load products');
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }, [filters, showStatus]);

  useEffect(() => {
    loadCategories();
    loadStatistics();
  }, [loadCategories, loadStatistics]);

  // Debounced reload so typing in the search box doesn't hammer the API.
  useEffect(() => {
    const t = setTimeout(loadProducts, 450);
    return () => clearTimeout(t);
  }, [loadProducts]);

  // ------------------------------------------------------------------
  // Derived
  // ------------------------------------------------------------------

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.category) count += 1;
    if (showStatus && filters.is_active) count += 1;
    if (filters.low_stock) count += 1;
    if (filters.out_of_stock) count += 1;
    return count;
  }, [filters, showStatus]);

  const allSelected =
    products.length > 0 && selectedProductIds.length === products.length;
  const someSelected =
    selectedProductIds.length > 0 && selectedProductIds.length < products.length;

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  const openCreate = () => {
    setEditingProduct(null);
    setShowForm(true);
  };

  const openView = (product) => {
    setViewProductId(product.id);
  };

  const openEdit = async (product) => {
    try {
      const full = await productsAPI.get(product.id);
      setEditingProduct(full.data);
      setShowForm(true);
      setViewProductId(null);
    } catch (error) {
      console.error('Error loading product details:', error);
      toast.error('Failed to load product details');
    }
  };

  const handleFormSaved = () => {
    setShowForm(false);
    setEditingProduct(null);
    setFilters(EMPTY_FILTERS);
    setTimeout(() => {
      loadProducts();
      loadStatistics();
    }, 200);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    if (makerCheckerOn && !deleteReason.trim()) {
      toast.warning('Enter a reason for deleting this product.');
      return;
    }
    setBusy(true);
    try {
      const payload = makerCheckerOn ? { reason: deleteReason.trim() } : {};
      const res = await productsAPI.delete(confirmDelete, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else {
        toast.success('Product deleted');
      }
      loadProducts();
      loadStatistics();
    } catch (error) {
      toast.error('Failed to delete product');
    } finally {
      setBusy(false);
      setConfirmDelete(null);
      setDeleteReason('');
    }
  };

  const confirmBulkDeleteAction = async () => {
    setBusy(true);
    try {
      await productsAPI.bulkDelete({ product_ids: selectedProductIds });
      toast.success(`Deleted ${selectedProductIds.length} product(s)`);
      setSelectedProductIds([]);
      loadProducts();
      loadStatistics();
    } catch (error) {
      toast.error('Failed to delete products');
    } finally {
      setBusy(false);
      setConfirmBulkDelete(false);
    }
  };

  const handleBulkActivate = async () => {
    if (selectedProductIds.length === 0) return;
    try {
      await productsAPI.bulkActivate({ product_ids: selectedProductIds });
      toast.success(`Activated ${selectedProductIds.length} product(s)`);
      setSelectedProductIds([]);
      loadProducts();
    } catch (error) {
      toast.error('Failed to activate products');
    }
  };

  const handleBulkDeactivate = async () => {
    if (selectedProductIds.length === 0) return;
    try {
      await productsAPI.bulkDeactivate({ product_ids: selectedProductIds });
      toast.success(`Deactivated ${selectedProductIds.length} product(s)`);
      setSelectedProductIds([]);
      loadProducts();
    } catch (error) {
      toast.error('Failed to deactivate products');
    }
  };

  const toggleProductSelection = (id) => {
    setSelectedProductIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    setSelectedProductIds(allSelected ? [] : products.map((p) => p.id));
  };

  // --- CSV ---

  const handleExport = async () => {
    try {
      toast.info('Exporting products…');
      const response = await productsAPI.export();
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `products_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Products exported');
    } catch (error) {
      console.error('Export error:', error);
      toast.error(
        'Failed to export products: ' + (error.response?.data?.error || error.message)
      );
    }
  };

  const handleDownloadTemplate = () => {
    const csvHeaders = catalogOnly
      ? [
          'name',
          'sku',
          'barcode',
          'category',
          'subcategory',
          'stock_quantity',
          'unit',
          'description',
          'track_stock',
          'has_variants',
          'available_sizes',
          'available_colors',
        ]
      : [
          'name',
          'sku',
          'barcode',
          'category',
          'subcategory',
          'mrp',
          'selling_price',
          'cost',
          'stock_quantity',
          'low_stock_threshold',
          'reorder_quantity',
          'unit',
          'description',
          'supplier',
          'supplier_contact',
          'tax_rate',
          'is_taxable',
          'track_stock',
          'is_active',
          'has_variants',
          'available_sizes',
          'available_colors',
        ];
    const sampleRow = catalogOnly
      ? [
          'Sample Product',
          'SKU-001',
          '1234567890123',
          'Electronics',
          'Mobile Phones',
          '10',
          'piece',
          'Sample product description',
          'true',
          'false',
          '',
          '',
        ]
      : [
          'Sample Product',
          'SKU-001',
          '1234567890123',
          'Electronics',
          'Mobile Phones',
          '1000.00',
          '800.00',
          '50',
          '10',
          '20',
          'piece',
          'Sample product description',
          'Supplier Name',
          'supplier@example.com',
          '16',
          'true',
          'true',
          'true',
          'false',
          '',
          '',
        ];
    const csvContent = ['\ufeff', csvHeaders.join(','), sampleRow.join(',')].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'products_import_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    toast.success(
      catalogOnly
        ? 'Catalog template downloaded — add products; manager sets prices later.'
        : 'Template downloaded — fill it in and re-import.'
    );
  };

  const handleImport = async (file) => {
    if (!file) return;
    try {
      toast.info('Importing products…');
      const formData = new FormData();
      formData.append('file', file);
      const response = await productsAPI.importCSV(formData);

      loadProducts();
      loadStatistics();

      const data = response.data || {};
      let message = data.message || 'Products imported';
      if (data.errors && data.errors.length > 0) {
        message += ` · ${data.errors.length} error(s) — see console.`;
        console.warn('Import errors:', data.errors);
      }
      toast.success(message, 8000);
    } catch (error) {
      const msg =
        error.response?.data?.error || error.message || 'Failed to import products';
      toast.error(`Failed to import products: ${msg}`, 8000);
      console.error('Import error:', error.response?.data || error);
    }
  };

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <PageShell>
        <PageHeader
          title="Products"
          description={
            catalogOnly
              ? 'Add products or import a list. Your manager will set prices before items go on sale.'
              : canAdjustStock
                ? 'Manage your catalog. Stock changes use Adjust stock (audited); the Stock column is not edited inline.'
                : 'Add, edit, and bulk-manage your catalog.'
          }
        >
          <div className="flex flex-wrap items-center gap-2">
            {(csvEnabled || catalogOnly) && (
              <>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">
                  <FileText className="h-4 w-4" />
                  CSV
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  {catalogOnly ? 'Import catalog' : 'Spreadsheet'}
                </DropdownMenuLabel>
                <DropdownMenuItem onClick={handleDownloadTemplate}>
                  <Download className="mr-2 h-4 w-4" />
                  Download template
                </DropdownMenuItem>
                {csvEnabled && !catalogOnly && (
                  <DropdownMenuItem onClick={handleExport}>
                    <Download className="mr-2 h-4 w-4" />
                    Export products
                  </DropdownMenuItem>
                )}
                {csvEnabled && (
                  <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                  <Upload className="mr-2 h-4 w-4" />
                  Import from CSV
                </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleImport(file);
                e.target.value = '';
              }}
            />
              </>
            )}
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              Add product
            </Button>
          </div>
        </PageHeader>

        {/* --- Summary stats --- */}
        <SummaryStats statistics={statistics} />

        {/* --- Filter toolbar --- */}
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          categories={categories}
          activeCount={activeFilterCount}
          showProductStatus={showStatus}
        />

        {/* --- Bulk action bar --- */}
        {bulkEnabled && selectedProductIds.length > 0 && !catalogOnly && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/40 bg-primary/5 px-4 py-2.5">
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="default">{selectedProductIds.length} selected</Badge>
              <button
                type="button"
                onClick={() => setSelectedProductIds([])}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Clear selection
              </button>
            </div>
            <div className="flex items-center gap-2">
              {showStatus && (
                <>
              <Button variant="outline" size="sm" onClick={handleBulkActivate}>
                Activate
              </Button>
              <Button variant="outline" size="sm" onClick={handleBulkDeactivate}>
                Deactivate
              </Button>
                </>
              )}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setConfirmBulkDelete(true)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            </div>
          </div>
        )}

        {/* --- Table --- */}
        <div className="overflow-hidden rounded-lg border bg-background">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {bulkEnabled && !catalogOnly && (
                  <th className="px-4 py-2.5">
                    <input
                      type="checkbox"
                      aria-label="Select all"
                      checked={allSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = someSelected;
                      }}
                      onChange={toggleSelectAll}
                      className="h-4 w-4 rounded border-input text-primary focus:ring-1 focus:ring-ring"
                    />
                  </th>
                  )}
                  <th className="px-4 py-2.5 text-left font-medium">Product</th>
                  <th className="px-4 py-2.5 text-left font-medium">Category</th>
                  {!catalogOnly && (
                    <>
                      {showMrp && (
                      <th className="px-4 py-2.5 text-right font-medium">MRP</th>
                      )}
                      <th className="px-4 py-2.5 text-right font-medium">Selling</th>
                      {showCost && fieldAccess.cost && (
                      <th className="px-4 py-2.5 text-right font-medium">Cost</th>
                      )}
                    </>
                  )}
                  {catalogOnly && (
                    <th className="px-4 py-2.5 text-right font-medium">Price</th>
                  )}
                  <th className="px-4 py-2.5 text-right font-medium">Stock</th>
                  {showStatus && (
                    <th className="px-4 py-2.5 text-left font-medium">Status</th>
                  )}
                  <th className="px-4 py-2.5 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading && products.length === 0 ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : products.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12">
                      <EmptyProducts
                        onCreate={openCreate}
                        hasFilters={!!filters.search || activeFilterCount > 0}
                      />
                    </td>
                  </tr>
                ) : (
                  products.map((product) => (
                    <ProductRow
                      key={product.id}
                      product={product}
                      selected={selectedProductIds.includes(product.id)}
                      onToggle={() => toggleProductSelection(product.id)}
                      onView={() => openView(product)}
                      onEdit={() => openEdit(product)}
                      onDelete={() => setConfirmDelete(product.id)}
                      onAdjustStock={
                        canAdjustStock && product.track_stock
                          ? () => setAdjustStockProduct(product)
                          : undefined
                      }
                      catalogOnly={catalogOnly}
                      showProductStatus={showStatus}
                      bulkEnabled={bulkEnabled}
                      showMrp={showMrp}
                      showCost={showCost && fieldAccess.cost}
                      showSku={showSku}
                      showLowStock={showLowStock}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      {/* --- Form modal (legacy, untouched) --- */}
      {adjustStockProduct && (
        <StockAdjustmentModal
          product={adjustStockProduct}
          onClose={() => setAdjustStockProduct(null)}
          onSave={() => {
            setAdjustStockProduct(null);
            loadProducts();
            loadStatistics();
          }}
        />
      )}

      {viewProductId ? (
        <ProductDetailPanel
          productId={viewProductId}
          fieldAccess={fieldAccess}
          productModuleSettings={productModuleSettings}
          storeSettings={storeSettings}
          onClose={() => setViewProductId(null)}
          onEdit={(fullProduct) => {
            setViewProductId(null);
            openEdit(fullProduct);
          }}
        />
      ) : null}

      {showForm && (
        <ProductForm
          product={editingProduct}
          categories={categories}
          catalogOnly={catalogOnly}
          fieldAccess={fieldAccess}
          financialFieldsLocked={financialFieldsLocked}
          showProductStatus={showStatus}
          showCost={showCost}
          showMrp={showMrp}
          onClose={() => {
            setShowForm(false);
            setEditingProduct(null);
          }}
          onSave={handleFormSaved}
        />
      )}

      {/* --- Confirms --- */}
      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete product"
        message={
          makerCheckerOn
            ? 'Submit a delete proposal for checker approval. The product stays active until approved.'
            : 'Are you sure you want to delete this product? This action cannot be undone.'
        }
        confirmText={makerCheckerOn ? 'Submit for approval' : 'Delete product'}
        cancelText="Cancel"
        type="danger"
        busy={busy}
        onConfirm={confirmDeleteAction}
        onCancel={() => {
          if (busy) return;
          setConfirmDelete(null);
          setDeleteReason('');
        }}
      >
        {makerCheckerOn && confirmDelete ? (
          <ChangeReasonField context="catalog" value={deleteReason} onChange={setDeleteReason} />
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        isOpen={confirmBulkDelete}
        title="Delete selected products?"
        message={`This will permanently remove ${selectedProductIds.length} product(s). Their sales history will be preserved.`}
        confirmText={`Delete ${selectedProductIds.length} product(s)`}
        cancelText="Cancel"
        type="danger"
        busy={busy}
        onConfirm={confirmBulkDeleteAction}
        onCancel={() => (busy ? null : setConfirmBulkDelete(false))}
      />
      </PageShell>
  );
};

function SummaryStats({ statistics }) {
  if (!statistics) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
    );
  }

  const items = [
    {
      label: 'Total products',
      value: statistics.total_products ?? '-',
      icon: Package,
      tone: 'default',
    },
    {
      label: 'Active',
      value: statistics.active_products ?? '-',
      icon: Package,
      tone: 'success',
    },
    {
      label: 'Low stock',
      value: statistics.low_stock_count ?? '-',
      icon: AlertCircle,
      tone: 'warning',
    },
    {
      label: 'Out of stock',
      value: statistics.out_of_stock_count ?? '-',
      icon: XCircle,
      tone: 'destructive',
    },
  ];

  const toneClasses = {
    default: 'text-foreground',
    success: 'text-success',
    warning: 'text-warning',
    destructive: 'text-destructive',
  };

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map(({ label, value, icon: Icon, tone }) => (
        <div
          key={label}
          className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3"
        >
          <div className={cn('flex h-9 w-9 items-center justify-center rounded-md bg-muted', toneClasses[tone])}>
            <Icon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </div>
            <div className={cn('text-lg font-semibold tabular-nums', toneClasses[tone])}>
              {value}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function FilterBar({ filters, setFilters, categories, activeCount, showProductStatus: showStatus = true }) {
  const update = (patch) => setFilters((prev) => ({ ...prev, ...patch }));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[260px] flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={filters.search}
            onChange={(e) => update({ search: e.target.value })}
            placeholder="Search by name or barcode…"
            className="h-10 pl-9"
          />
          {filters.search && (
            <button
              type="button"
              onClick={() => update({ search: '' })}
              className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              <Filter className="h-4 w-4" />
              Filters
              {activeCount > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {activeCount}
                </Badge>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64">
            {showStatus && (
              <>
            <DropdownMenuLabel>Status</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => update({ is_active: '' })}>
              <span className={cn(filters.is_active === '' && 'font-semibold')}>
                All statuses
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => update({ is_active: 'true' })}>
              <span className={cn(filters.is_active === 'true' && 'font-semibold')}>
                Active only
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => update({ is_active: 'false' })}>
              <span className={cn(filters.is_active === 'false' && 'font-semibold')}>
                Inactive only
              </span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuLabel>Stock</DropdownMenuLabel>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                update({ low_stock: !filters.low_stock });
              }}
            >
              <input
                type="checkbox"
                readOnly
                checked={filters.low_stock}
                className="mr-2 h-3.5 w-3.5 rounded border-input"
              />
              Low stock only
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                update({ out_of_stock: !filters.out_of_stock });
              }}
            >
              <input
                type="checkbox"
                readOnly
                checked={filters.out_of_stock}
                className="mr-2 h-3.5 w-3.5 rounded border-input"
              />
              Out of stock only
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => setFilters({ ...EMPTY_FILTERS, search: filters.search })}
              className="text-destructive focus:text-destructive"
            >
              Reset all filters
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Category chips — keeps the most common filter one tap away */}
      {categories.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <CategoryChip
            label="All categories"
            active={!filters.category}
            onClick={() => update({ category: '' })}
          />
          {categories.slice(0, 12).map((cat) => (
            <CategoryChip
              key={cat.id}
              label={cat.name}
              active={String(filters.category) === String(cat.id)}
              onClick={() => update({ category: cat.id })}
            />
          ))}
          {categories.length > 12 && (
            <span className="ml-1 text-xs text-muted-foreground">
              +{categories.length - 12} more
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function CategoryChip({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-background text-foreground hover:bg-accent'
      )}
    >
      {label}
    </button>
  );
}

function ProductRow({
  product,
  selected,
  onToggle,
  onView,
  onEdit,
  onDelete,
  onAdjustStock,
  catalogOnly = false,
  showProductStatus: showStatus = true,
  bulkEnabled = true,
  showMrp = true,
  showCost = true,
  showSku = false,
  showLowStock = true,
}) {
  const sellingPrice = parseFloat(product.selling_price ?? product.price ?? 0);
  const pricePending = catalogOnly && sellingPrice <= 0;

  return (
    <tr
      className={cn(
        'transition-colors hover:bg-muted/40',
        selected && 'bg-primary/5',
        showStatus && !product.is_active && 'opacity-60'
      )}
    >
      {bulkEnabled && !catalogOnly && (
      <td className="px-4 py-3">
        <input
          type="checkbox"
          aria-label={`Select ${product.name}`}
          checked={selected}
          onChange={onToggle}
          className="h-4 w-4 rounded border-input text-primary focus:ring-1 focus:ring-ring"
        />
      </td>
      )}
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <ProductThumb product={product} />
          <div className="min-w-0">
            <button
              type="button"
              onClick={onView}
              className="line-clamp-1 text-left font-medium text-foreground underline-offset-2 hover:text-primary hover:underline"
            >
              {product.name}
            </button>
            <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              {showSku && product.sku && (
                <span className="font-mono text-[11px]">{product.sku}</span>
              )}
              {product.has_variants && (
                <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
                  {(product.available_sizes_detail?.length || 0) +
                    (product.available_colors_detail?.length || 0)}{' '}
                  variants
                </Badge>
              )}
              {showLowStock && product.is_low_stock && (
                <Badge variant="warning" className="px-1.5 py-0 text-[10px]">
                  Low stock
                </Badge>
              )}
              <PendingApprovalBadges pendingApproval={product.pending_approval} />
            </div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="text-sm text-foreground">{product.category_name || '—'}</div>
        {product.subcategory_name && (
          <div className="text-xs text-muted-foreground">→ {product.subcategory_name}</div>
        )}
      </td>
      {!catalogOnly && (
        <>
          {showMrp && (
          <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
            {formatCurrency(product.mrp ?? product.price)}
          </td>
          )}
          <td className={cn('px-4 py-3 text-right', SELLING_PRICE_CLASS)}>
            {formatCurrency(product.selling_price ?? product.price)}
          </td>
          {showCost && (
          <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
            {formatCurrency(product.cost)}
          </td>
          )}
        </>
      )}
      {catalogOnly && (
        <td className="px-4 py-3 text-right text-sm">
          {pricePending ? (
            <Badge variant="outline" className="font-normal text-muted-foreground">
              Pending manager
            </Badge>
          ) : (
            <span className={SELLING_PRICE_CLASS}>
              {formatCurrency(product.selling_price ?? product.price)}
            </span>
          )}
        </td>
      )}
      <td className="px-4 py-3 text-right">
        <StockCell product={product} onAdjustStock={onAdjustStock} />
      </td>
      {showStatus && (
      <td className="px-4 py-3">
        <Badge variant={product.is_active ? 'success' : 'outline'}>
          {product.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </td>
      )}
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={onEdit} aria-label="Edit product">
            <Pencil className="h-3.5 w-3.5" />
            <span className="sr-only sm:not-sr-only sm:ml-1">Edit</span>
          </Button>
          {!catalogOnly && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" aria-label="More actions">
                <MoreHorizontal className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onAdjustStock ? (
                <DropdownMenuItem onClick={onAdjustStock}>
                  <Scale className="mr-2 h-3.5 w-3.5" />
                  Adjust stock
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuItem
                onClick={onDelete}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-3.5 w-3.5" />
                Delete product
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          )}
        </div>
      </td>
    </tr>
  );
}

function ProductThumb({ product }) {
  const imageSrc = resolveMediaUrl(product.image_url || product.image);
  if (imageSrc) {
    return (
      <img
        src={imageSrc}
        alt={product.name}
        className="h-10 w-10 shrink-0 rounded-md border bg-muted object-cover"
        loading="lazy"
      />
    );
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border bg-muted text-muted-foreground">
      <ImageIcon className="h-4 w-4" />
    </div>
  );
}

function StockCell({ product, onAdjustStock }) {
  if (!product.track_stock) {
    return <span className="text-xs text-muted-foreground">Not tracked</span>;
  }
  const qty = parseInt(product.stock_quantity, 10) || 0;
  const lowThreshold = parseInt(product.low_stock_threshold, 10) || 0;
  const tone =
    qty <= 0
      ? 'text-destructive'
      : lowThreshold > 0 && qty <= lowThreshold
      ? 'text-warning'
      : 'text-foreground';
  const qtyEl = (
    <span className={cn('font-semibold tabular-nums', tone)}>{qty}</span>
  );
  if (!onAdjustStock) {
    return qtyEl;
  }
  return (
    <button
      type="button"
      onClick={onAdjustStock}
      className="group inline-flex flex-col items-end rounded-md px-1 py-0.5 text-right hover:bg-muted/80"
      title="Adjust stock (+/- quantity with audit trail)"
    >
      {qtyEl}
      <span className="text-[10px] font-normal text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
        Adjust
      </span>
    </button>
  );
}

function EmptyProducts({ onCreate, hasFilters }) {
  if (hasFilters) {
    return (
      <div className="flex flex-col items-center gap-2 text-muted-foreground">
        <Package className="h-8 w-8 opacity-50" />
        <p className="font-medium text-foreground">No products match these filters</p>
        <p className="text-sm">Try clearing some filters or adjust your search.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-3 text-muted-foreground">
      <Package className="h-10 w-10 opacity-40" />
      <div>
        <p className="font-medium text-foreground">No products yet</p>
        <p className="text-sm">Add your first product to start selling.</p>
      </div>
      <Button onClick={onCreate} size="sm">
        <Plus className="h-4 w-4" />
        Add your first product
      </Button>
    </div>
  );
}

export default Products;
