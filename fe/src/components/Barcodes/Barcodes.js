import React, { useState, useEffect } from 'react';
import { barcodesAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import '../../styles/shared.css';
import './Barcodes.css';

const Barcodes = () => {
  const [products, setProducts] = useState([]);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [barcodeFormat, setBarcodeFormat] = useState('code128');
  const [labelSettings, setLabelSettings] = useState({
    include_name: true,
    include_price: false,
    quantity: 1,
    label_width: 4,
    label_height: 2,
  });
  const [previewBarcode, setPreviewBarcode] = useState(null);
  const [previewProduct, setPreviewProduct] = useState(null);
  const [filters, setFilters] = useState({
    search: '',
    has_barcode: 'all', // all, yes, no
  });
  const [showConfirmGenerate, setShowConfirmGenerate] = useState(false);

  useEffect(() => {
    loadProducts();
  }, [filters]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const params = { is_active: 'true' };
      if (filters.search) params.search = filters.search;
      
      const response = await productsAPI.list(params);
      const productsData = response.data.results || response.data || [];
      let filtered = Array.isArray(productsData) ? productsData : [];
      
      // Filter by barcode status
      if (filters.has_barcode === 'yes') {
        filtered = filtered.filter(p => p.barcode);
      } else if (filters.has_barcode === 'no') {
        filtered = filtered.filter(p => !p.barcode);
      }
      
      setProducts(filtered);
    } catch (error) {
      toast.error('Failed to load products');
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectProduct = (productId) => {
    setSelectedProducts(prev => {
      if (prev.includes(productId)) {
        return prev.filter(id => id !== productId);
      }
      return [...prev, productId];
    });
  };

  const handleSelectAll = () => {
    if (selectedProducts.length === products.length) {
      setSelectedProducts([]);
    } else {
      setSelectedProducts(products.map(p => p.id));
    }
  };

  const handleGenerateMissing = () => {
    setShowConfirmGenerate(true);
  };

  const confirmGenerateMissing = async () => {
    setShowConfirmGenerate(false);
    setGenerating(true);
    try {
      const response = await barcodesAPI.generateMissing({
        barcode_format: barcodeFormat, // Changed from 'format' to avoid DRF format suffix conflict
        prefix: 'BC',
      });
      
      const message = `Generated ${response.data.generated} barcodes${response.data.errors > 0 ? `. ${response.data.errors} errors.` : '.'}`;
      toast.success(message);
      loadProducts();
    } catch (error) {
      toast.error('Failed to generate barcodes: ' + (error.response?.data?.error || error.message));
    } finally {
      setGenerating(false);
    }
  };

  const handlePreviewBarcode = async (product) => {
    try {
      // Use barcode or SKU for preview
      const barcodeValue = product.barcode || product.sku;
      if (!barcodeValue) {
        toast.warning('Product must have a barcode or SKU to generate preview');
        return;
      }

      // Build query parameters - use 'barcode_format' instead of 'format' to avoid DRF format suffix conflict
      const params = {
        product_id: product.id,
        barcode_format: barcodeFormat,
        width: 2,
        height: 100,
        include_text: 'true',
      };
      
      const response = await barcodesAPI.generate(params);
      
      if (response && response.data) {
        // Validate response structure
        if (response.data.image && response.data.barcode) {
          setPreviewBarcode(response.data);
          setPreviewProduct(product);
          toast.success('Barcode preview generated successfully!');
        } else {
          toast.error('Failed to generate preview: Invalid response structure from server');
        }
      } else {
        toast.error('Failed to generate preview: Invalid response from server');
      }
    } catch (error) {
      
      let errorMessage = 'Unknown error occurred';
      if (error.response) {
        // Server responded with error
        errorMessage = error.response.data?.error || 
                      error.response.data?.detail || 
                      error.response.data?.message ||
                      `Server error: ${error.response.status} ${error.response.statusText}`;
      } else if (error.request) {
        // Request was made but no response received
        errorMessage = 'No response from server. Please check your connection.';
      } else {
        // Error in request setup
        errorMessage = error.message || 'Error setting up request';
      }
      
      toast.error(`Failed to generate preview: ${errorMessage}`);
    }
  };

  const [showPrintPreview, setShowPrintPreview] = useState(false);
  const [printPreviewData, setPrintPreviewData] = useState(null);

  const handlePrintLabels = async () => {
    if (selectedProducts.length === 0) {
      toast.warning('Please select at least one product');
      return;
    }

    // Show preview first
    try {
      // Generate preview for first selected product
      const firstProduct = products.find(p => selectedProducts.includes(p.id));
      if (firstProduct) {
        const previewResponse = await barcodesAPI.generate({
          product_id: firstProduct.id,
          barcode_format: barcodeFormat, // Changed from 'format' to avoid DRF format suffix conflict
          width: 2,
          height: 100,
          include_text: true,
        });
        setPrintPreviewData({
          product: firstProduct,
          preview: previewResponse.data,
          totalProducts: selectedProducts.length,
        });
        setShowPrintPreview(true);
      }
    } catch (error) {
      // If preview fails, show error
      toast.error('Failed to generate preview: ' + (error.response?.data?.error || error.message));
    }
  };

  const handlePrint = () => {
    // Open browser print dialog
    window.print();
  };

  const handleDownloadPDF = async () => {
    setGenerating(true);
    try {
      const productIds = printPreviewData ? selectedProducts : [previewProduct?.id].filter(Boolean);
      const response = await barcodesAPI.printLabels({
        product_ids: productIds,
        barcode_format: barcodeFormat,
        ...labelSettings,
      }, { responseType: 'blob' });
      
      // Create blob URL and download
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const filename = printPreviewData 
        ? 'barcode_labels.pdf' 
        : `${previewProduct?.name || 'barcode'}_barcode.pdf`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('Barcode labels downloaded successfully');
    } catch (error) {
      toast.error('Failed to download labels: ' + (error.response?.data?.error || error.message));
    } finally {
      setGenerating(false);
    }
  };

  const handlePrintSingle = async (product) => {
    // Always show preview first
    await handlePreviewBarcode(product);
  };

  const productsWithoutBarcode = products.filter(p => !p.barcode).length;

  return (
    <Layout>
      <div className="barcodes-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1>Barcode Management & Printing</h1>
        </div>
        <div className="page-header-actions">
          <button
            onClick={handleGenerateMissing}
            disabled={generating || productsWithoutBarcode === 0}
            className="btn btn-primary"
          >
            {generating ? 'Generating...' : `Generate Missing (${productsWithoutBarcode})`}
          </button>
        </div>
      </div>

      <div className="barcodes-controls">
        <div className="controls-section">
          <h3>Barcode/QR Code Format</h3>
          <div className="format-options">
            <label className="format-option">
              <input
                type="radio"
                name="barcodeFormat"
                value="code128"
                checked={barcodeFormat === 'code128'}
                onChange={(e) => setBarcodeFormat(e.target.value)}
              />
              <span>Code 128</span>
            </label>
            <label className="format-option">
              <input
                type="radio"
                name="barcodeFormat"
                value="ean13"
                checked={barcodeFormat === 'ean13'}
                onChange={(e) => setBarcodeFormat(e.target.value)}
              />
              <span>EAN-13</span>
            </label>
            <label className="format-option">
              <input
                type="radio"
                name="barcodeFormat"
                value="ean8"
                checked={barcodeFormat === 'ean8'}
                onChange={(e) => setBarcodeFormat(e.target.value)}
              />
              <span>EAN-8</span>
            </label>
            <label className="format-option qr-option">
              <input
                type="radio"
                name="barcodeFormat"
                value="qrcode"
                checked={barcodeFormat === 'qrcode'}
                onChange={(e) => setBarcodeFormat(e.target.value)}
              />
              <span>📱 QR Code</span>
            </label>
          </div>
          <SearchableSelect
            value={barcodeFormat}
            onChange={(e) => setBarcodeFormat(e.target.value)}
            className="format-select-mobile"
            options={[
              { id: 'code128', name: 'Code 128' },
              { id: 'ean13', name: 'EAN-13' },
              { id: 'ean8', name: 'EAN-8' },
              { id: 'qrcode', name: '📱 QR Code' }
            ]}
            placeholder="Select Format"
          />
        </div>

        <div className="controls-section">
          <h3>Label Settings</h3>
          <div className="label-settings">
            <label>
              <input
                type="checkbox"
                checked={labelSettings.include_name}
                onChange={(e) => setLabelSettings({ ...labelSettings, include_name: e.target.checked })}
              />
              Include Product Name
            </label>
            <label>
              <input
                type="checkbox"
                checked={labelSettings.include_price}
                onChange={(e) => setLabelSettings({ ...labelSettings, include_price: e.target.checked })}
              />
              Include Price
            </label>
            <div className="setting-row">
              <label>Quantity per Product:</label>
              <input
                type="number"
                min="1"
                max="10"
                value={labelSettings.quantity}
                onChange={(e) => setLabelSettings({ ...labelSettings, quantity: parseInt(e.target.value) || 1 })}
                className="quantity-input"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="barcodes-filters">
        <input
          type="text"
          placeholder="Search products..."
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="search-input"
        />
        <SearchableSelect
          value={filters.has_barcode}
          onChange={(e) => setFilters({ ...filters, has_barcode: e.target.value })}
          className="filter-select"
          options={[
            { id: 'all', name: 'All Products' },
            { id: 'yes', name: 'With Barcode' },
            { id: 'no', name: 'Without Barcode' }
          ]}
          placeholder="All Products"
        />
      </div>

      <div className="barcodes-actions">
        <div className="selection-info">
          <span>{selectedProducts.length} selected</span>
          <button onClick={handleSelectAll} className="btn-link">
            {selectedProducts.length === products.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>
        <button
          onClick={handlePrintLabels}
          disabled={selectedProducts.length === 0 || generating}
          className="btn-primary"
        >
          {generating ? 'Generating PDF...' : `Print ${selectedProducts.length} Label(s)`}
        </button>
      </div>

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
                    onChange={handleSelectAll}
                  />
                </th>
                <th>Product</th>
                <th>SKU</th>
                <th>Barcode</th>
                <th>Price</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty-state">
                    No products found
                  </td>
                </tr>
              ) : (
                products.map(product => (
                  <tr key={product.id} className={!product.barcode ? 'no-barcode' : ''}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedProducts.includes(product.id)}
                        onChange={() => handleSelectProduct(product.id)}
                      />
                    </td>
                    <td>
                      <div className="product-info">
                        <div className="product-name">{product.name}</div>
                        {product.has_variants && (
                          <div className="variant-info">
                            {(product.available_sizes_detail?.length || 0) > 0 && (
                              <span>{product.available_sizes_detail.length} sizes</span>
                            )}
                            {(product.available_sizes_detail?.length || 0) > 0 && (product.available_colors_detail?.length || 0) > 0 && ' • '}
                            {(product.available_colors_detail?.length || 0) > 0 && (
                              <span>{product.available_colors_detail.length} colors</span>
                            )}
                          </div>
                        )}
                        {product.category_name && (
                          <div className="product-category">
                            {product.category_name}
                            {product.subcategory_name && ` → ${product.subcategory_name}`}
                          </div>
                        )}
                      </div>
                    </td>
                    <td>{product.sku}</td>
                    <td>
                      {product.barcode ? (
                        <span className="barcode-value">{product.barcode}</span>
                      ) : (
                        <span className="no-barcode-badge">No Barcode</span>
                      )}
                    </td>
                    <td>{formatCurrency(product.price)}</td>
                    <td>
                      <div className="action-buttons">
                        <button
                          onClick={() => handlePreviewBarcode(product)}
                          className="btn-preview"
                          disabled={!product.barcode && !product.sku}
                          title={!product.barcode && !product.sku ? 'Product needs a barcode or SKU' : 'Preview barcode'}
                        >
                          Preview
                        </button>
                        <button
                          onClick={() => handlePrintSingle(product)}
                          className="btn-print"
                          disabled={!product.barcode && !product.sku}
                          title={!product.barcode && !product.sku ? 'Product needs a barcode or SKU' : 'Print barcode label'}
                        >
                          Print
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

      {previewBarcode && previewProduct && (
        <div className="modal-overlay print-preview-container" onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }}>
          <div className="modal-content barcode-preview" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Barcode Preview - {previewProduct.name}</h2>
              <button onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }} className="close-btn">×</button>
            </div>
            <div className="preview-content">
              <div className="barcode-image-container">
                <img src={previewBarcode.image} alt="Barcode" className="barcode-image" />
              </div>
              <div className="barcode-info">
                <p><strong>Format:</strong> {previewBarcode.format?.toUpperCase() || 'CODE128'}</p>
                <p><strong>Value:</strong> {previewBarcode.barcode}</p>
                <p><strong>Product:</strong> {previewProduct.name}</p>
                <p><strong>SKU:</strong> {previewProduct.sku}</p>
              </div>
              <div className="preview-actions">
                <button
                  onClick={handlePrint}
                  className="btn-primary"
                >
                  Print
                </button>
                <button
                  onClick={handleDownloadPDF}
                  className="btn-secondary"
                  disabled={generating}
                >
                  {generating ? 'Downloading...' : 'Download PDF'}
                </button>
                <button
                  onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }}
                  className="btn-secondary"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Print Preview Modal for Multiple Products */}
      {showPrintPreview && printPreviewData && (
        <div className="modal-overlay" onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }}>
          <div className="modal-content barcode-preview" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Print Preview - {printPreviewData.totalProducts} Product(s)</h2>
              <button onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }} className="close-btn">×</button>
            </div>
            <div className="preview-content">
              <div className="barcode-image-container">
                <img src={printPreviewData.preview.image} alt="Barcode" className="barcode-image" />
              </div>
              <div className="barcode-info">
                <p><strong>Format:</strong> {printPreviewData.preview.format?.toUpperCase() || 'CODE128'}</p>
                <p><strong>Sample Product:</strong> {printPreviewData.product.name}</p>
                <p><strong>Total Products:</strong> {printPreviewData.totalProducts}</p>
                <p><strong>Quantity per Product:</strong> {labelSettings.quantity}</p>
                <p><strong>Total Labels:</strong> {printPreviewData.totalProducts * labelSettings.quantity}</p>
              </div>
              <div className="preview-actions">
                <button
                  onClick={handlePrint}
                  className="btn-primary"
                >
                  Print
                </button>
                <button
                  onClick={handleDownloadPDF}
                  className="btn-secondary"
                  disabled={generating}
                >
                  {generating ? 'Downloading...' : 'Download PDF'}
                </button>
                <button
                  onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

        {/* Confirm Generate Dialog */}
        <ConfirmDialog
          isOpen={showConfirmGenerate}
          title="Generate Missing Barcodes"
          message="Generate barcodes for all products without barcodes?"
          onConfirm={confirmGenerateMissing}
          onCancel={() => setShowConfirmGenerate(false)}
          confirmText="Generate"
          cancelText="Cancel"
          type="primary"
        />
      </div>
    </Layout>
  );
};

export default Barcodes;

