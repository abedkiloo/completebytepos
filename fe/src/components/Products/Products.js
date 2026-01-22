import React, { useState, useEffect } from 'react';
import { productsAPI, categoriesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import SearchableSelect from '../Shared/SearchableSelect';
import ProductForm from './ProductForm';
import ProductStatistics from './ProductStatistics';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import '../../styles/shared.css';
import './Products.css';

const Products = () => {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    is_active: '',
    low_stock: false,
    out_of_stock: false,
  });
  const [statistics, setStatistics] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);
  const [showCSVSection, setShowCSVSection] = useState(false);

  useEffect(() => {
    loadProducts();
    loadCategories();
    loadStatistics();
  }, [filters]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const params = { page_size: 1000 }; // Request more items to avoid pagination issues
      if (filters.search) params.search = filters.search;
      if (filters.category) params.category = filters.category;
      if (filters.is_active !== '') params.is_active = filters.is_active;
      if (filters.low_stock) params.low_stock = 'true';
      if (filters.out_of_stock) params.out_of_stock = 'true';

      const response = await productsAPI.list(params);
      // Handle paginated or direct array response
      const productsData = response.data.results || response.data || [];
      const productsArray = Array.isArray(productsData) ? productsData : [];
      console.log(`Loaded ${productsArray.length} products with filters:`, filters);
      setProducts(productsArray);
    } catch (error) {
      console.error('Error loading products:', error);
      toast.error('Failed to load products');
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await categoriesAPI.list();
      // Handle paginated or direct array response
      const categoriesData = response.data.results || response.data || [];
      setCategories(Array.isArray(categoriesData) ? categoriesData : []);
    } catch (error) {
      console.error('Error loading categories:', error);
      setCategories([]);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await productsAPI.statistics();
      setStatistics(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const handleDelete = (id) => {
    setConfirmDelete(id);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;

    try {
      await productsAPI.delete(confirmDelete);
      loadProducts();
      loadStatistics();
      toast.success('Product deleted successfully');
    } catch (error) {
      toast.error('Failed to delete product');
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleBulkDelete = () => {
    if (selectedProducts.length === 0) {
      toast.warning('Please select products to delete');
      return;
    }
    setConfirmBulkDelete(true);
  };

  const confirmBulkDeleteAction = async () => {
    try {
      await productsAPI.bulkDelete({ product_ids: selectedProducts });
      setSelectedProducts([]);
      loadProducts();
      loadStatistics();
      toast.success('Products deleted successfully');
    } catch (error) {
      toast.error('Failed to delete products');
    } finally {
      setConfirmBulkDelete(false);
    }
  };

  const handleBulkActivate = async () => {
    if (selectedProducts.length === 0) {
      toast.warning('Please select products to activate');
      return;
    }

    try {
      await productsAPI.bulkActivate({ product_ids: selectedProducts });
      setSelectedProducts([]);
      loadProducts();
      toast.success('Products activated successfully');
    } catch (error) {
      toast.error('Failed to activate products');
    }
  };

  const handleBulkDeactivate = async () => {
    if (selectedProducts.length === 0) {
      toast.warning('Please select products to deactivate');
      return;
    }

    try {
      await productsAPI.bulkDeactivate({ product_ids: selectedProducts });
      setSelectedProducts([]);
      loadProducts();
      toast.success('Products deactivated successfully');
    } catch (error) {
      toast.error('Failed to deactivate products');
    }
  };

  const handleExport = async () => {
    try {
      toast.info('Exporting products...', 2000);
      const response = await productsAPI.export();
      // Handle blob response
      const blob = response.data instanceof Blob 
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
      toast.success('Products exported successfully! File downloaded.');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export products: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleDownloadTemplate = () => {
    // CSV template with all required and optional fields matching export format
    const csvHeaders = [
      'name',
      'sku',
      'barcode',
      'category',
      'subcategory',
      'price',
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
      'available_colors'
    ];

    // Create CSV content with headers, instructions, and example rows
    const csvContent = [
      // BOM for Excel compatibility
      '\ufeff',
      csvHeaders.join(','),
      // Example row 1
      [
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
        ''
      ].join(','),
      // Example row 2 with variants
      [
        'Product with Variants',
        'SKU-002',
        '9876543210987',
        'Clothing',
        'T-Shirts',
        '1500.00',
        '1000.00',
        '100',
        '20',
        '50',
        'piece',
        'T-shirt with size and color options',
        'Fashion Supplier',
        'fashion@example.com',
        '16',
        'true',
        'true',
        'true',
        'true',
        'Small,Medium,Large',
        'Red,Blue,Green'
      ].join(','),
      '', // Empty row
      '# ==========================================',
      '# CSV IMPORT TEMPLATE - PRODUCTS',
      '# ==========================================',
      '#',
      '# INSTRUCTIONS:',
      '# 1. Fill in product details in the rows above (remove example rows if needed)',
      '# 2. REQUIRED FIELDS: name, sku, price, cost',
      '# 3. OPTIONAL FIELDS: All other fields can be left empty',
      '#',
      '# FIELD DESCRIPTIONS:',
      '# - name: Product name (required)',
      '# - sku: Stock Keeping Unit - must be unique (required)',
      '# - barcode: Product barcode (optional)',
      '# - category: Main category name (optional, will be created if not exists)',
      '# - subcategory: Subcategory name (optional, must be child of category)',
      '# - price: Selling price (required, numbers only, no currency symbols)',
      '# - cost: Cost price (required, numbers only)',
      '# - stock_quantity: Current stock level (default: 0)',
      '# - low_stock_threshold: Alert when stock falls below this (default: 10)',
      '# - reorder_quantity: Quantity to order when restocking (default: 50)',
      '# - unit: Unit of measurement - piece, kg, g, l, ml, box, pack, bottle, can (default: piece)',
      '# - description: Product description (optional)',
      '# - supplier: Supplier name (optional)',
      '# - supplier_contact: Supplier contact info (optional)',
      '# - tax_rate: Tax rate percentage (default: 0)',
      '# - is_taxable: true or false (default: true)',
      '# - track_stock: true or false (default: true)',
      '# - is_active: true or false (default: true)',
      '# - has_variants: true or false (default: false)',
      '# - available_sizes: Comma-separated size names (e.g., "Small,Medium,Large")',
      '# - available_colors: Comma-separated color names (e.g., "Red,Blue,Green")',
      '#',
      '# IMPORTANT NOTES:',
      '# - Boolean fields: Use "true" or "false" (lowercase)',
      '# - Numeric fields: Use numbers only, no currency symbols or commas',
      '# - Categories: Will be created automatically if they don\'t exist',
      '# - SKU: Must be unique. If SKU exists, product will be updated',
      '# - Save this file as CSV format before importing',
      '#',
      '# After filling the template:',
      '# 1. Save as CSV file',
      '# 2. Click "Import CSV" button',
      '# 3. Select your CSV file',
      '# 4. Wait for import to complete',
      '# =========================================='
    ].join('\n');

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'products_import_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    toast.success('CSV template downloaded! Fill it with your product data and import it.');
  };

  const handleImport = async (file) => {
    try {
      if (!file) {
        toast.error('Please select a CSV file');
        return;
      }
      
      toast.info('Importing products...', 3000);
      const formData = new FormData();
      formData.append('file', file);
      const response = await productsAPI.importCSV(formData);
      
      loadProducts();
      loadStatistics();
      
      const data = response.data;
      let message = data.message || 'Products imported successfully';
      
      if (data.errors && data.errors.length > 0) {
        const errorCount = data.errors.length;
        message += ` (${errorCount} error${errorCount > 1 ? 's' : ''} - see console for details)`;
        console.warn('Import errors:', data.errors);
      }
      
      toast.success(message, 8000);
    } catch (error) {
      let errorMessage = 'Failed to import products';
      if (error.response?.data?.error) {
        errorMessage += ': ' + error.response.data.error;
      } else if (error.message) {
        errorMessage += ': ' + error.message;
      }
      toast.error(errorMessage, 8000);
      console.error('Import error:', error.response?.data || error);
    }
  };

  const toggleProductSelection = (id) => {
    setSelectedProducts(prev =>
      prev.includes(id)
        ? prev.filter(p => p !== id)
        : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedProducts.length === products.length) {
      setSelectedProducts([]);
    } else {
      setSelectedProducts(products.map(p => p.id));
    }
  };

  return (
    <Layout>
      <div className="products-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1>Product Management</h1>
        </div>
        <div className="page-header-actions">
          <button onClick={() => { setEditingProduct(null); setShowForm(true); }} className="btn btn-primary btn-add-product">
            <span>+</span>
            <span>Add Product</span>
          </button>
        </div>
      </div>

      {/* CSV Operations Section - Collapsible */}
      <div className={`csv-operations-section ${showCSVSection ? 'expanded' : ''}`}>
        <div 
          className="csv-operations-header-clickable" 
          onClick={() => setShowCSVSection(!showCSVSection)}
          title={showCSVSection ? "Click to collapse" : "Click to expand CSV operations"}
        >
          <div className="csv-operations-header-content">
            <h2>📊 CSV Import & Export</h2>
            <p className="csv-operations-subtitle">Bulk manage your products using CSV files</p>
          </div>
          <div className="csv-operations-toggle">
            <span className="csv-toggle-icon">{showCSVSection ? '▼' : '▶'}</span>
            <span className="csv-toggle-text">{showCSVSection ? 'Collapse' : 'Expand'}</span>
          </div>
        </div>
        {showCSVSection && (
          <div className="csv-operations-content">
            <div className="csv-operations-buttons">
              <button onClick={handleDownloadTemplate} className="btn btn-csv-template">
                <span className="btn-icon">📥</span>
                <div className="btn-content">
                  <span className="btn-label">Download Template</span>
                  <span className="btn-hint">Get CSV format with all fields</span>
                </div>
              </button>
              <button onClick={handleExport} className="btn btn-csv-export">
                <span className="btn-icon">📤</span>
                <div className="btn-content">
                  <span className="btn-label">Export Products</span>
                  <span className="btn-hint">Download all products as CSV</span>
                </div>
              </button>
              <label className="btn btn-csv-import">
                <span className="btn-icon">📥</span>
                <div className="btn-content">
                  <span className="btn-label">Import Products</span>
                  <span className="btn-hint">Upload CSV file to add/update</span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => e.target.files[0] && handleImport(e.target.files[0])}
                  style={{ display: 'none' }}
                />
              </label>
            </div>
            <div className="csv-operations-info">
              <p><strong>Quick Guide:</strong> Download template → Fill with product data → Import to add/update products. Existing SKUs will be updated, new SKUs will be created.</p>
            </div>
          </div>
        )}
      </div>

      {/* Page Description and Instructions - Collapsible */}
      <div className={`products-page-description ${showInstructions ? 'expanded' : ''}`}>
        <div 
          className="page-description-header" 
          onClick={() => setShowInstructions(!showInstructions)}
          title={showInstructions ? "Click to collapse" : "Click to expand guide"}
        >
          <h2>Product Management Guide</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="toggle-icon">{showInstructions ? '▼' : '▶'}</span>
            <span style={{ fontSize: '0.75rem', color: '#6b7280', fontWeight: 500 }}>
              {showInstructions ? 'Collapse' : 'Expand'}
            </span>
          </div>
        </div>
        {showInstructions && (
          <div className="page-description-content">
            <div className="instructions-grid">
              <div className="instruction-section">
                <h3>📝 Adding Products</h3>
                <ol>
                  <li>Click <strong>"Add Product"</strong> button (green button) to create a new product</li>
                  <li>Fill in product details (name, SKU, price, cost, etc.)</li>
                  <li>Select category and optionally subcategory</li>
                  <li>Set stock quantity and thresholds</li>
                  <li>Click <strong>"Save"</strong> to add the product</li>
                </ol>
              </div>
              <div className="instruction-section">
                <h3>📊 CSV Operations</h3>
                <p>Use the <strong>"CSV Import & Export"</strong> section above for bulk product management. All CSV operations are available there with clear buttons and instructions.</p>
              </div>
              <div className="instruction-section">
                <h3>🔍 Managing Products</h3>
                <ul>
                  <li>Use search bar to find products by name, SKU, or barcode</li>
                  <li>Filter by category, status, or stock level</li>
                  <li>Click <strong>"Edit"</strong> to modify product details</li>
                  <li>Click <strong>"Delete"</strong> to remove products</li>
                  <li>Use checkboxes for bulk operations (activate/deactivate/delete)</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>

      {statistics && <ProductStatistics statistics={statistics} />}

      <div className="products-filters">
        <input
          type="text"
          placeholder="Search products..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="filter-input"
        />
        <SearchableSelect
          value={filters.category || ''}
          onChange={(e) => setFilters({ ...filters, category: e.target.value })}
          options={[
            { id: '', name: 'All Categories' },
            ...(Array.isArray(categories) ? categories.map(cat => ({ id: cat.id, name: cat.name })) : [])
          ]}
          placeholder="Filter by category..."
          name="category"
          searchable={true}
          className="filter-select"
        />
        <SearchableSelect
          value={filters.is_active || ''}
          onChange={(e) => setFilters({ ...filters, is_active: e.target.value })}
          options={[
            { id: '', name: 'All Status' },
            { id: 'true', name: 'Active' },
            { id: 'false', name: 'Inactive' },
          ]}
          placeholder="Filter by status..."
          name="is_active"
          searchable={true}
          className="filter-select"
        />
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.low_stock}
            onChange={(e) => setFilters({ ...filters, low_stock: e.target.checked })}
          />
          Low Stock
        </label>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.out_of_stock}
            onChange={(e) => setFilters({ ...filters, out_of_stock: e.target.checked })}
          />
          Out of Stock
        </label>
      </div>

      {selectedProducts.length > 0 && (
        <div className="bulk-actions">
          <span>{selectedProducts.length} selected</span>
          <button onClick={handleBulkActivate}>Activate</button>
          <button onClick={handleBulkDeactivate}>Deactivate</button>
          <button onClick={handleBulkDelete} className="danger">Delete</button>
        </div>
      )}

      {loading ? (
        <div className="loading">Loading products...</div>
      ) : (
        <div className="products-table-container">
          <table className="products-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={selectedProducts.length === products.length && products.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Image</th>
                <th>Product</th>
                <th>Category</th>
                <th>SKU</th>
                <th>Price</th>
                <th>Cost</th>
                <th>Unit</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan="10" className="empty-state" style={{ padding: '3rem', textAlign: 'center' }}>
                    No products found
                  </td>
                </tr>
              ) : (
                products.map(product => (
                  <tr key={product.id} className={`product-row ${!product.is_active ? 'inactive' : ''}`}>
                    <td className="checkbox-cell">
                      <input
                        type="checkbox"
                        checked={selectedProducts.includes(product.id)}
                        onChange={() => toggleProductSelection(product.id)}
                      />
                    </td>
                    <td className="product-image-cell">
                      {product.image_url ? (
                        <img src={product.image_url} alt={product.name} className="product-thumb" />
                      ) : (
                        <div className="product-thumb-placeholder">No Image</div>
                      )}
                    </td>
                    <td className="product-name-cell-compact">
                      <div className="product-name-compact">{product.name}</div>
                      {product.has_variants && (
                        <span className="variant-badge-compact">
                          {(product.available_sizes_detail?.length || 0) + (product.available_colors_detail?.length || 0)} variants
                        </span>
                      )}
                      {product.is_low_stock && (
                        <span className="low-stock-badge-compact">Low Stock</span>
                      )}
                    </td>
                    <td className="product-category-cell-compact">
                      <div className="category-main">{product.category_name || '-'}</div>
                      {product.subcategory_name && (
                        <div className="category-sub">→ {product.subcategory_name}</div>
                      )}
                    </td>
                    <td className="product-sku-cell-compact">
                      <span className="sku-value-compact">{product.sku || 'N/A'}</span>
                    </td>
                    <td className="product-price-cell-compact">{formatCurrency(product.price)}</td>
                    <td className="product-cost-cell-compact">{formatCurrency(product.cost)}</td>
                    <td className="product-unit-cell-compact">{product.unit}</td>
                    <td className="product-status-cell-compact">
                      <span className={`status-badge-compact ${product.is_active ? 'active' : 'inactive'}`}>
                        {product.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="product-actions-cell-compact">
                      <div className="action-buttons-compact">
                        <button
                          onClick={async () => {
                            try {
                              // Fetch full product details for editing
                              const fullProduct = await productsAPI.get(product.id);
                              setEditingProduct(fullProduct.data);
                              setShowForm(true);
                            } catch (error) {
                              console.error('Error loading product details:', error);
                              toast.error('Failed to load product details');
                            }
                          }}
                          className="btn-edit-compact"
                          title="Edit product"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(product.id)}
                          className="btn-delete-compact"
                          title="Delete product"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <ProductForm
          product={editingProduct}
          categories={categories}
          onClose={() => {
            setShowForm(false);
            setEditingProduct(null);
          }}
          onSave={() => {
            setShowForm(false);
            setEditingProduct(null);
            // Clear filters to ensure new product is visible
            setFilters({
              search: '',
              category: '',
              is_active: '',
              low_stock: false,
              out_of_stock: false,
            });
            // Reload after a short delay to ensure backend has processed
            setTimeout(() => {
              loadProducts();
              loadStatistics();
            }, 200);
          }}
        />
      )}

      {/* Confirm Delete Dialogs */}
      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete Product"
        message="Are you sure you want to delete this product?"
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />

      <ConfirmDialog
        isOpen={confirmBulkDelete}
        title="Delete Products"
        message={`Are you sure you want to delete ${selectedProducts.length} product(s)?`}
        onConfirm={confirmBulkDeleteAction}
        onCancel={() => setConfirmBulkDelete(false)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
      </div>
    </Layout>
  );
};

export default Products;
