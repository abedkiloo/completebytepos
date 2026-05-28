import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeftRight,
  Package,
  Plus,
  Scale,
  History,
} from 'lucide-react';
import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../../utils/formatters';
import { isFeatureEnabledInAny } from '../../utils/moduleSettings';
import SearchableSelect from '../Shared/SearchableSelect';
import StockAdjustmentModal from './StockAdjustmentModal';
import StockPurchaseModal from './StockPurchaseModal';
import StockHistoryModal from './StockHistoryModal';
import StockTransferModal from './StockTransferModal';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  FilterField,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  SummaryCard,
} from '../page';
import { cn } from '../../lib/cn';

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

  const movementBadgeVariant = (type) => {
    const map = {
      sale: 'destructive',
      purchase: 'success',
      adjustment: 'warning',
      transfer: 'secondary',
    };
    return map[type] || 'outline';
  };

  if (loading && activeTab === 'movements' && movements.length === 0) {
    return (
      <PageLoading rows={8} showStats />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Inventory"
          description="Track stock movements, low stock alerts, and valuation."
        >
          <Button onClick={handlePurchase}>
            <Plus className="h-4 w-4" />
            Record purchase
          </Button>
          {isFeatureEnabledInAny(['inventory', 'stock'], 'stock_adjustments') && (
            <Button variant="outline" onClick={handleAdjustment}>
              <Scale className="h-4 w-4" />
              Adjust
            </Button>
          )}
          {isFeatureEnabledInAny(['inventory', 'stock'], 'stock_transfers') && (
            <Button variant="outline" onClick={handleTransfer}>
              <ArrowLeftRight className="h-4 w-4" />
              Transfer
            </Button>
          )}
        </PageHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
            <TabsTrigger value="movements">Movements</TabsTrigger>
            <TabsTrigger value="low_stock">
              Low stock ({lowStockProducts.length})
            </TabsTrigger>
            <TabsTrigger value="out_of_stock">
              Out of stock ({outOfStockProducts.length})
            </TabsTrigger>
            <TabsTrigger value="report">Overview</TabsTrigger>
          </TabsList>

          <TabsContent value="movements" className="mt-4 space-y-4">
            <FilterBar>
              <FilterField label="Type" className="min-w-[160px]">
                <SearchableSelect
                  value={filters.movement_type || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, movement_type: e.target.value })
                  }
                  options={[
                    { id: '', name: 'All types' },
                    { id: 'sale', name: 'Sale' },
                    { id: 'purchase', name: 'Purchase' },
                    { id: 'adjustment', name: 'Adjustment' },
                    { id: 'return', name: 'Return' },
                    { id: 'damage', name: 'Damage' },
                    { id: 'transfer', name: 'Transfer' },
                    { id: 'waste', name: 'Waste' },
                    { id: 'expired', name: 'Expired' },
                  ]}
                  placeholder="All types"
                  name="movement_type"
                />
              </FilterField>
              <FilterField label="From">
                <Input
                  type="date"
                  value={filters.date_from}
                  onChange={(e) =>
                    setFilters({ ...filters, date_from: e.target.value })
                  }
                />
              </FilterField>
              <FilterField label="To">
                <Input
                  type="date"
                  value={filters.date_to}
                  onChange={(e) =>
                    setFilters({ ...filters, date_to: e.target.value })
                  }
                />
              </FilterField>
            </FilterBar>

            {loading ? (
              <PageLoading rows={6} />
            ) : movements.length === 0 ? (
              <EmptyState
                icon={Package}
                title="No movements yet"
                description="Record a purchase or complete a sale to see stock activity."
                actionLabel="Record purchase"
                onAction={handlePurchase}
              />
            ) : (
              <DataTable>
                <DataTableHeader>
                  <DataTableHead>Date</DataTableHead>
                  <DataTableHead>Product</DataTableHead>
                  <DataTableHead>Type</DataTableHead>
                  <DataTableHead align="right">Qty</DataTableHead>
                  <DataTableHead align="right">After</DataTableHead>
                  <DataTableHead>User</DataTableHead>
                  <DataTableHead align="right">Actions</DataTableHead>
                </DataTableHeader>
                <DataTableBody>
                  {movements.map((movement) => (
                    <DataTableRow key={movement.id}>
                      <DataTableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDateTime(movement.created_at)}
                      </DataTableCell>
                      <DataTableCell>
                        <p className="font-medium">{movement.product_name}</p>
                        <p className="text-xs text-muted-foreground">{movement.product_sku}</p>
                      </DataTableCell>
                      <DataTableCell>
                        <Badge
                          variant={movementBadgeVariant(movement.movement_type)}
                          className="capitalize"
                        >
                          {movement.movement_type}
                        </Badge>
                      </DataTableCell>
                      <DataTableCell
                        align="right"
                        className={cn(
                          'font-semibold tabular-nums',
                          movement.quantity > 0 ? 'text-success' : 'text-destructive'
                        )}
                      >
                        {movement.quantity > 0 ? '+' : ''}
                        {formatNumber(movement.quantity)}
                      </DataTableCell>
                      <DataTableCell align="right" className="tabular-nums">
                        {formatNumber(movement.stock_after || 0)}
                      </DataTableCell>
                      <DataTableCell className="text-muted-foreground">
                        {movement.user_name || '—'}
                      </DataTableCell>
                      <DataTableCell align="right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            handleViewHistory(
                              movement.product_detail || {
                                id: movement.product,
                                name: movement.product_name,
                                sku: movement.product_sku,
                              }
                            )
                          }
                        >
                          <History className="h-4 w-4" />
                        </Button>
                      </DataTableCell>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            )}
          </TabsContent>

          <TabsContent value="low_stock" className="mt-4">
            {loading ? (
              <PageLoading rows={4} />
            ) : lowStockProducts.length === 0 ? (
              <EmptyState
                icon={Package}
                title="No low-stock items"
                description="Products above their threshold appear healthy."
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {lowStockProducts.map((product) => (
                  <StockProductCard
                    key={product.id}
                    product={product}
                    tone="warning"
                    label="Low stock"
                    onReorder={() => {
                      setSelectedProduct(product);
                      setShowPurchaseModal(true);
                    }}
                    onHistory={() => handleViewHistory(product)}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="out_of_stock" className="mt-4">
            {loading ? (
              <PageLoading rows={4} />
            ) : outOfStockProducts.length === 0 ? (
              <EmptyState
                icon={Package}
                title="Nothing out of stock"
                description="All tracked products have quantity on hand."
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {outOfStockProducts.map((product) => (
                  <StockProductCard
                    key={product.id}
                    product={product}
                    tone="destructive"
                    label="Out of stock"
                    onReorder={() => {
                      setSelectedProduct(product);
                      setShowPurchaseModal(true);
                    }}
                    onHistory={() => handleViewHistory(product)}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="report" className="mt-4">
            {loading || !report ? (
              <PageLoading rows={4} showStats />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <SummaryCard icon={Package} label="Total products" value={report.total_products} />
                <SummaryCard icon={Package} label="Tracked" value={report.tracked_products} />
                <SummaryCard
                  icon={Package}
                  label="Low stock"
                  value={report.low_stock_count}
                  tone="warning"
                />
                <SummaryCard
                  icon={Package}
                  label="Out of stock"
                  value={report.out_of_stock_count}
                  tone="destructive"
                />
                <SummaryCard
                  icon={Package}
                  label="Inventory value"
                  value={formatCurrency(report.total_inventory_value)}
                  tone="success"
                />
                <SummaryCard
                  icon={Package}
                  label="Movements today"
                  value={report.total_movements_today}
                />
                <SummaryCard
                  icon={Package}
                  label="Movements this month"
                  value={report.total_movements_this_month}
                />
              </div>
            )}
          </TabsContent>
        </Tabs>

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
      </PageShell>
  );
};

function StockProductCard({ product, tone, label, onReorder, onHistory }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-base leading-snug">{product.name}</CardTitle>
        <Badge variant={tone === 'destructive' ? 'destructive' : 'warning'}>{label}</Badge>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>SKU {product.sku}</p>
        <p>
          Stock:{' '}
          <span className="font-semibold text-foreground">
            {formatNumber(product.stock_quantity ?? 0)}
          </span>
        </p>
        <p>Threshold: {formatNumber(product.low_stock_threshold)}</p>
        <div className="flex gap-2 pt-2">
          <Button size="sm" onClick={onReorder}>
            Reorder
          </Button>
          <Button size="sm" variant="outline" onClick={onHistory}>
            History
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default Inventory;
