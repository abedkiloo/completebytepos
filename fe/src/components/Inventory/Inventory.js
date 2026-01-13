import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { inventoryAPI, productsAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import { isFeatureEnabled, isFeatureEnabledInAny } from '../../utils/moduleSettings';
import Layout from '../Layout/Layout';
import StockAdjustmentModal from './StockAdjustmentModal';
import StockPurchaseModal from './StockPurchaseModal';
import StockHistoryModal from './StockHistoryModal';
import StockTransferModal from './StockTransferModal';
import '../../styles/shared.css';
import './Inventory.css';

const Inventory = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [movements, setMovements] = useState([]);
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [outOfStockProducts, setOutOfStockProducts] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false);
  const [showPurchaseModal, setShowPurchaseModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [filters, setFilters] = useState({
    movement_type: '',
    product: '',
    date_from: '',
    date_to: '',
  });
  const [activeTab, setActiveTab] = useState('movements'); // movements, low_stock, out_of_stock, report
  const [, forceUpdate] = useState(0);

  // Listen for module settings updates
  useEffect(() => {
    const handleModuleSettingsUpdate = () => {
      // Force re-render to check updated module settings
      forceUpdate(prev => prev + 1);
    };
    
    window.addEventListener('moduleSettingsUpdated', handleModuleSettingsUpdate);
    return () => {
      window.removeEventListener('moduleSettingsUpdated', handleModuleSettingsUpdate);
    };
  }, []);

  // Handle URL parameters to open appropriate modals/tabs
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const action = params.get('action');
    const view = params.get('view');

    if (action === 'adjust' && isFeatureEnabledInAny(['inventory', 'stock'], 'stock_adjustments')) {
      setShowAdjustmentModal(true);
      // Clean URL after opening modal
      navigate('/inventory', { replace: true });
    } else if (action === 'transfer' && isFeatureEnabledInAny(['inventory', 'stock'], 'stock_transfers')) {
      setShowTransferModal(true);
      // Clean URL after opening modal
      navigate('/inventory', { replace: true });
    } else if (view === 'movements') {
      setActiveTab('movements');
      // Clean URL
      navigate('/inventory', { replace: true });
    }
  }, [location.search, navigate]);

  useEffect(() => {
    loadData();
  }, [filters, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'movements') {
        await loadMovements();
      } else if (activeTab === 'low_stock') {
        await loadLowStock();
      } else if (activeTab === 'out_of_stock') {
        await loadOutOfStock();
      } else if (activeTab === 'report') {
        await loadReport();
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMovements = async () => {
    try {
      const params = {};
      if (filters.movement_type) params.movement_type = filters.movement_type;
      if (filters.product) params.product = filters.product;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;

      const response = await inventoryAPI.list(params);
      setMovements(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading movements:', error);
      setMovements([]);
    }
  };

  const loadLowStock = async () => {
    try {
      const response = await inventoryAPI.lowStock();
      setLowStockProducts(response.data);
    } catch (error) {
      console.error('Error loading low stock:', error);
      setLowStockProducts([]);
    }
  };

  const loadOutOfStock = async () => {
    try {
      const response = await inventoryAPI.outOfStock();
      setOutOfStockProducts(response.data);
    } catch (error) {
      console.error('Error loading out of stock:', error);
      setOutOfStockProducts([]);
    }
  };

  const loadReport = async () => {
    try {
      const response = await inventoryAPI.report();
      setReport(response.data);
    } catch (error) {
      console.error('Error loading report:', error);
    }
  };

  const handleAdjustment = () => {
    setSelectedProduct(null);
    setShowAdjustmentModal(true);
  };

  const handlePurchase = () => {
    setSelectedProduct(null);
    setShowPurchaseModal(true);
  };

  const handleTransfer = () => {
    setSelectedProduct(null);
    setShowTransferModal(true);
  };

  const handleViewHistory = (product) => {
    setSelectedProduct(product);
    setShowHistoryModal(true);
  };

  const getMovementTypeColor = (type) => {
    const colors = {
      'sale': '#ef4444',
      'purchase': '#10b981',
      'adjustment': '#f59e0b',
      'return': '#3b82f6',
      'damage': '#dc2626',
      'transfer': '#8b5cf6',
      'waste': '#f97316',
      'expired': '#6b7280',
    };
    return colors[type] || '#6b7280';
  };

  return (
    <Layout>
      <div className="inventory-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1>Inventory Management</h1>
        </div>
        <div className="page-header-actions" style={{ display: 'flex', flexWrap: 'nowrap', gap: '0.75rem', alignItems: 'center' }}>
          <button onClick={handlePurchase} className="btn btn-primary">
            <span>+</span>
            <span>Record Purchase</span>
          </button>
          {isFeatureEnabledInAny(['inventory', 'stock'], 'stock_adjustments') && (
            <button onClick={handleAdjustment} className="btn btn-secondary">
              Adjust Stock
            </button>
          )}
          {isFeatureEnabledInAny(['inventory', 'stock'], 'stock_transfers') && (
            <button onClick={handleTransfer} className="btn btn-secondary">
              Transfer Stock
            </button>
          )}
        </div>
      </div>

      <div className="inventory-tabs">
        <button
          className={activeTab === 'movements' ? 'active' : ''}
          onClick={() => setActiveTab('movements')}
        >
          Stock Movements
        </button>
        <button
          className={activeTab === 'low_stock' ? 'active' : ''}
          onClick={() => setActiveTab('low_stock')}
        >
          Low Stock ({lowStockProducts.length})
        </button>
        <button
          className={activeTab === 'out_of_stock' ? 'active' : ''}
          onClick={() => setActiveTab('out_of_stock')}
        >
          Out of Stock ({outOfStockProducts.length})
        </button>
        <button
          className={activeTab === 'report' ? 'active' : ''}
          onClick={() => setActiveTab('report')}
        >
          Report
        </button>
      </div>

      {activeTab === 'movements' && (
        <div className="inventory-content">
          <div className="filters-section">
            <select
              value={filters.movement_type}
              onChange={(e) => setFilters({ ...filters, movement_type: e.target.value })}
              className="filter-select"
            >
              <option value="">All Types</option>
              <option value="sale">Sale</option>
              <option value="purchase">Purchase</option>
              <option value="adjustment">Adjustment</option>
              <option value="return">Return</option>
              <option value="damage">Damage</option>
              <option value="transfer">Transfer</option>
              <option value="waste">Waste</option>
              <option value="expired">Expired</option>
            </select>
            <input
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
              className="filter-input"
              placeholder="From Date"
            />
            <input
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
              className="filter-input"
              placeholder="To Date"
            />
          </div>

          {loading ? (
            <div className="loading">Loading movements...</div>
          ) : (
            <div className="movements-table-container">
              <table className="movements-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Product</th>
                    <th>Type</th>
                    <th>Quantity</th>
                    <th>Unit Cost</th>
                    <th>Total Cost</th>
                    <th>Stock Before</th>
                    <th>Stock After</th>
                    <th>User</th>
                    <th>Reference</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.length === 0 ? (
                    <tr>
                      <td colSpan="11" className="empty-state">
                        No stock movements found
                      </td>
                    </tr>
                  ) : (
                    movements.map(movement => (
                      <tr key={movement.id}>
                        <td>{formatDateTime(movement.created_at)}</td>
                        <td>
                          <div className="product-info">
                            <div className="product-name">{movement.product_name}</div>
                            <div className="product-sku">{movement.product_sku}</div>
                          </div>
                        </td>
                        <td>
                          <span
                            className="movement-type-badge"
                            style={{ backgroundColor: getMovementTypeColor(movement.movement_type) }}
                          >
                            {movement.movement_type}
                          </span>
                        </td>
                        <td className={movement.quantity > 0 ? 'positive' : 'negative'}>
                          {movement.quantity > 0 ? '+' : ''}{formatNumber(movement.quantity)}
                        </td>
                        <td>{movement.unit_cost ? formatCurrency(movement.unit_cost) : '-'}</td>
                        <td>{movement.total_cost ? formatCurrency(movement.total_cost) : '-'}</td>
                        <td>{formatNumber(movement.stock_before || 0)}</td>
                        <td>{formatNumber(movement.stock_after || 0)}</td>
                        <td>{movement.user_name || '-'}</td>
                        <td>{movement.reference || '-'}</td>
                        <td>
                          <button
                            onClick={() => handleViewHistory(
                              movement.product_detail || {
                                id: movement.product,
                                name: movement.product_name,
                                sku: movement.product_sku
                              }
                            )}
                            className="btn-link"
                          >
                            History
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'low_stock' && (
        <div className="inventory-content">
          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <div className="products-grid">
              {lowStockProducts.length === 0 ? (
                <div className="empty-state">No products with low stock</div>
              ) : (
                lowStockProducts.map(product => (
                  <div key={product.id} className="product-card">
                    <div className="product-header">
                      <h3>{product.name}</h3>
                      <span className="low-stock-badge">Low Stock</span>
                    </div>
                    <div className="product-details">
                      <p><strong>SKU:</strong> {product.sku}</p>
                      {product.has_variants && (
                        <p><strong>Variants:</strong> 
                          {(product.available_sizes_detail?.length || 0) > 0 && (
                            <span>{product.available_sizes_detail.length} sizes</span>
                          )}
                          {(product.available_sizes_detail?.length || 0) > 0 && (product.available_colors_detail?.length || 0) > 0 && ' • '}
                          {(product.available_colors_detail?.length || 0) > 0 && (
                            <span>{product.available_colors_detail.length} colors</span>
                          )}
                        </p>
                      )}
                      {product.subcategory_name && (
                        <p><strong>Subcategory:</strong> {product.subcategory_name}</p>
                      )}
                      <p><strong>Current Stock:</strong> {formatNumber(product.stock_quantity)}</p>
                      <p><strong>Low Stock Threshold:</strong> {formatNumber(product.low_stock_threshold)}</p>
                      <p><strong>Reorder Quantity:</strong> {formatNumber(product.reorder_quantity || 0)}</p>
                      <p><strong>Unit:</strong> {product.unit}</p>
                    </div>
                    <div className="product-actions">
                      <button
                        onClick={() => {
                          setSelectedProduct(product);
                          setShowPurchaseModal(true);
                        }}
                        className="btn-primary"
                      >
                        Reorder
                      </button>
                      <button
                        onClick={() => handleViewHistory(product)}
                        className="btn-secondary"
                      >
                        View History
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'out_of_stock' && (
        <div className="inventory-content">
          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <div className="products-grid">
              {outOfStockProducts.length === 0 ? (
                <div className="empty-state">No products out of stock</div>
              ) : (
                outOfStockProducts.map(product => (
                  <div key={product.id} className="product-card danger">
                    <div className="product-header">
                      <h3>{product.name}</h3>
                      <span className="out-of-stock-badge">Out of Stock</span>
                    </div>
                    <div className="product-details">
                      <p><strong>SKU:</strong> {product.sku}</p>
                      <p><strong>Current Stock:</strong> 0</p>
                      <p><strong>Reorder Quantity:</strong> {formatNumber(product.reorder_quantity || 0)}</p>
                      <p><strong>Unit:</strong> {product.unit}</p>
                    </div>
                    <div className="product-actions">
                      <button
                        onClick={() => {
                          setSelectedProduct(product);
                          setShowPurchaseModal(true);
                        }}
                        className="btn-primary"
                      >
                        Restock
                      </button>
                      <button
                        onClick={() => handleViewHistory(product)}
                        className="btn-secondary"
                      >
                        View History
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'report' && report && (
        <div className="inventory-content">
          <div className="report-grid">
            <div className="report-card">
              <h3>Total Products</h3>
              <p className="stat-value">{report.total_products}</p>
            </div>
            <div className="report-card">
              <h3>Tracked Products</h3>
              <p className="stat-value">{report.tracked_products}</p>
            </div>
            <div className="report-card warning">
              <h3>Low Stock</h3>
              <p className="stat-value">{report.low_stock_count}</p>
            </div>
            <div className="report-card danger">
              <h3>Out of Stock</h3>
              <p className="stat-value">{report.out_of_stock_count}</p>
            </div>
            <div className="report-card success">
              <h3>Total Inventory Value</h3>
              <p className="stat-value">{formatCurrency(report.total_inventory_value)}</p>
            </div>
            <div className="report-card">
              <h3>Movements Today</h3>
              <p className="stat-value">{report.total_movements_today}</p>
            </div>
            <div className="report-card">
              <h3>Movements This Month</h3>
              <p className="stat-value">{report.total_movements_this_month}</p>
            </div>
          </div>
        </div>
      )}

      {showAdjustmentModal && isFeatureEnabledInAny(['inventory', 'stock'], 'stock_adjustments') && (
        <StockAdjustmentModal
          product={selectedProduct}
          onClose={() => {
            setShowAdjustmentModal(false);
            setSelectedProduct(null);
          }}
          onSave={() => {
            setShowAdjustmentModal(false);
            setSelectedProduct(null);
            loadData();
          }}
        />
      )}

      {showPurchaseModal && (
        <StockPurchaseModal
          product={selectedProduct}
          onClose={() => {
            setShowPurchaseModal(false);
            setSelectedProduct(null);
          }}
          onSave={() => {
            setShowPurchaseModal(false);
            setSelectedProduct(null);
            loadData();
          }}
        />
      )}

      {showHistoryModal && selectedProduct && (
        <StockHistoryModal
          product={selectedProduct}
          onClose={() => {
            setShowHistoryModal(false);
            setSelectedProduct(null);
          }}
        />
      )}

      {showTransferModal && isFeatureEnabledInAny(['inventory', 'stock'], 'stock_transfers') && (
        <StockTransferModal
          isOpen={showTransferModal}
          product={selectedProduct}
          onClose={() => {
            setShowTransferModal(false);
            setSelectedProduct(null);
            navigate('/inventory', { replace: true });
          }}
          onSuccess={() => {
            loadData();
          }}
        />
      )}
      </div>
    </Layout>
  );
};

export default Inventory;
