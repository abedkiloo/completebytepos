import React, { useState, useEffect } from 'react';
import { barcodesAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { PageShell, PageHeader, PageLoading, FilterBar, SearchField, FilterField } from '../page';
import '../../styles/barcodePrint.css';

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
    <>
    <PageShell>
      <PageHeader
        title="Barcode management"
        description="Generate, preview, and print product barcode labels."
      >
        <Button
          onClick={handleGenerateMissing}
          disabled={generating || productsWithoutBarcode === 0}
        >
          {generating ? 'Generating…' : `Generate missing (${productsWithoutBarcode})`}
        </Button>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold">Barcode / QR format</h3>
          <div className="flex flex-wrap gap-3 text-sm">
            {[
              { id: 'code128', label: 'Code 128' },
              { id: 'ean13', label: 'EAN-13' },
              { id: 'ean8', label: 'EAN-8' },
              { id: 'qrcode', label: 'QR Code' },
            ].map((fmt) => (
              <label key={fmt.id} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="barcodeFormat"
                  value={fmt.id}
                  checked={barcodeFormat === fmt.id}
                  onChange={(e) => setBarcodeFormat(e.target.value)}
                />
                {fmt.label}
              </label>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold">Label settings</h3>
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={labelSettings.include_name}
                onChange={(e) => setLabelSettings({ ...labelSettings, include_name: e.target.checked })}
              />
              Include product name
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={labelSettings.include_price}
                onChange={(e) => setLabelSettings({ ...labelSettings, include_price: e.target.checked })}
              />
              Include price
            </label>
            <div className="flex items-center gap-2">
              <span>Quantity per product:</span>
              <Input
                type="number"
                min="1"
                max="10"
                className="h-8 w-20"
                value={labelSettings.quantity}
                onChange={(e) =>
                  setLabelSettings({ ...labelSettings, quantity: parseInt(e.target.value, 10) || 1 })
                }
              />
            </div>
          </div>
        </div>
      </div>

      <FilterBar className="mt-4">
        <SearchField
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          placeholder="Search products…"
          className="min-w-[200px] flex-[2]"
        />
        <FilterField label="Barcode">
          <SearchableSelect
            value={filters.has_barcode}
            onChange={(e) => setFilters({ ...filters, has_barcode: e.target.value })}
            options={[
              { id: 'all', name: 'All products' },
              { id: 'yes', name: 'With barcode' },
              { id: 'no', name: 'Without barcode' },
            ]}
            placeholder="All products"
          />
        </FilterField>
      </FilterBar>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">{selectedProducts.length} selected</span>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={handleSelectAll}>
            {selectedProducts.length === products.length ? 'Deselect all' : 'Select all'}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handlePrintLabels}
            disabled={selectedProducts.length === 0 || generating}
          >
            {generating ? 'Generating PDF…' : `Print ${selectedProducts.length} label(s)`}
          </Button>
        </div>
      </div>

      {loading ? (
        <PageLoading rows={8} />
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left">
              <tr>
                <th className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selectedProducts.length === products.length && products.length > 0}
                    onChange={handleSelectAll}
                    aria-label="Select all products"
                  />
                </th>
                <th className="px-3 py-2 font-medium">Product</th>
                <th className="px-3 py-2 font-medium">SKU</th>
                <th className="px-3 py-2 font-medium">Barcode</th>
                <th className="px-3 py-2 font-medium">Price</th>
                <th className="px-3 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-3 py-8 text-center text-muted-foreground">
                    No products found
                  </td>
                </tr>
              ) : (
                products.map((product) => (
                  <tr key={product.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedProducts.includes(product.id)}
                        onChange={() => handleSelectProduct(product.id)}
                        aria-label={`Select ${product.name}`}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="font-medium">{product.name}</div>
                      {product.category_name && (
                        <div className="text-xs text-muted-foreground">{product.category_name}</div>
                      )}
                    </td>
                    <td className="px-3 py-2">{product.sku}</td>
                    <td className="px-3 py-2">
                      {product.barcode ? (
                        <code className="text-xs">{product.barcode}</code>
                      ) : (
                        <Badge variant="secondary">No barcode</Badge>
                      )}
                    </td>
                    <td className="px-3 py-2">{formatCurrency(product.price)}</td>
                    <td className="px-3 py-2">
                      <div className="flex justify-end gap-1">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handlePreviewBarcode(product)}
                          disabled={!product.barcode && !product.sku}
                        >
                          Preview
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => handlePrintSingle(product)}
                          disabled={!product.barcode && !product.sku}
                        >
                          Print
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>

      {previewBarcode && previewProduct && (
        <div
          className="print-preview-container fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4"
          onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }}
        >
          <div className="barcode-print-dialog w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="barcode-print-header flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">Barcode Preview — {previewProduct.name}</h2>
              <button
                type="button"
                onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="barcode-print-body space-y-4 p-6">
              <div className="barcode-print-image-wrap rounded-md bg-muted/40 p-4 text-center">
                <img src={previewBarcode.image} alt="Barcode" className="mx-auto max-w-full" />
              </div>
              <div className="space-y-1 text-sm text-foreground">
                <p><strong>Format:</strong> {previewBarcode.format?.toUpperCase() || 'CODE128'}</p>
                <p><strong>Value:</strong> {previewBarcode.barcode}</p>
                <p><strong>Product:</strong> {previewProduct.name}</p>
                <p><strong>SKU:</strong> {previewProduct.sku}</p>
              </div>
              <div className="barcode-print-actions flex flex-wrap justify-end gap-2">
                <Button type="button" onClick={handlePrint}>Print</Button>
                <Button type="button" variant="outline" onClick={handleDownloadPDF} disabled={generating}>
                  {generating ? 'Downloading...' : 'Download PDF'}
                </Button>
                <Button type="button" variant="outline" onClick={() => { setPreviewBarcode(null); setPreviewProduct(null); }}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showPrintPreview && printPreviewData && (
        <div
          className="print-preview-container fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4"
          onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }}
        >
          <div className="barcode-print-dialog w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg border bg-background shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="barcode-print-header flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">Print Preview — {printPreviewData.totalProducts} Product(s)</h2>
              <button
                type="button"
                onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="barcode-print-body space-y-4 p-6">
              <div className="barcode-print-image-wrap rounded-md bg-muted/40 p-4 text-center">
                <img src={printPreviewData.preview.image} alt="Barcode" className="mx-auto max-w-full" />
              </div>
              <div className="space-y-1 text-sm text-foreground">
                <p><strong>Format:</strong> {printPreviewData.preview.format?.toUpperCase() || 'CODE128'}</p>
                <p><strong>Sample Product:</strong> {printPreviewData.product.name}</p>
                <p><strong>Total Products:</strong> {printPreviewData.totalProducts}</p>
                <p><strong>Quantity per Product:</strong> {labelSettings.quantity}</p>
                <p><strong>Total Labels:</strong> {printPreviewData.totalProducts * labelSettings.quantity}</p>
              </div>
              <div className="barcode-print-actions flex flex-wrap justify-end gap-2">
                <Button type="button" onClick={handlePrint}>Print</Button>
                <Button type="button" variant="outline" onClick={handleDownloadPDF} disabled={generating}>
                  {generating ? 'Downloading...' : 'Download PDF'}
                </Button>
                <Button type="button" variant="outline" onClick={() => { setShowPrintPreview(false); setPrintPreviewData(null); }}>
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

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
    </>
  );
};

export default Barcodes;

