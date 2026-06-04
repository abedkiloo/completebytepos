import React, { useState, useEffect, useMemo } from 'react';
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
import { useModuleSettings } from '../../hooks/useModuleSettings';
import {
  inventoryShowStockMovements,
  inventoryAdjustmentsEnabled,
  inventoryPurchasesEnabled,
  inventoryTransfersEnabled,
  inventoryShowLowStockAlerts,
  inventoryShowOutOfStockAlerts,
  inventoryReportEnabled,
  inventoryShowMovementCost,
} from '../../utils/inventoryDisplay';
import SearchableSelect from '../Shared/SearchableSelect';
import StockAdjustmentModal from './StockAdjustmentModal';
import StockPurchaseModal from './StockPurchaseModal';
import StockHistoryModal from './StockHistoryModal';
import StockTransferModal from './StockTransferModal';
import StockBulkAdjustModal from './StockBulkAdjustModal';
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
  const { settings: inventorySettings } = useModuleSettings('inventory');

  const canShowMovements = inventoryShowStockMovements(inventorySettings);
  const canAdjust =
    isFeatureEnabledInAny(['inventory', 'stock'], 'stock_adjustments') &&
    inventoryAdjustmentsEnabled(inventorySettings);
  const canPurchase = inventoryPurchasesEnabled(inventorySettings);
  const canTransfer =
    isFeatureEnabledInAny(['inventory', 'stock'], 'stock_transfers') &&
    inventoryTransfersEnabled(inventorySettings);
  const canShowLowStock = inventoryShowLowStockAlerts(inventorySettings);
  const canShowOutOfStock = inventoryShowOutOfStockAlerts(inventorySettings);
  const canShowReport = inventoryReportEnabled(inventorySettings);
  const showMovementCost = inventoryShowMovementCost(inventorySettings);
  const [movements, setMovements] = useState([]);
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [outOfStockProducts, setOutOfStockProducts] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false);
  const [showPurchaseModal, setShowPurchaseModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showBulkAdjustModal, setShowBulkAdjustModal] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [filters, setFilters] = useState({
    movement_type: '',
    product: '',
    date_from: '',
    date_to: '',
  });
  const firstAvailableTab = useMemo(() => {
    if (canShowMovements) return 'movements';
    if (canShowLowStock) return 'low_stock';
    if (canShowOutOfStock) return 'out_of_stock';
    if (canShowReport) return 'report';
    return 'movements';
  }, [canShowMovements, canShowLowStock, canShowOutOfStock, canShowReport]);

  const [activeTab, setActiveTab] = useState(firstAvailableTab);

  useEffect(() => {
    const allowed = {
      movements: canShowMovements,
      low_stock: canShowLowStock,
      out_of_stock: canShowOutOfStock,
      report: canShowReport,
    };
    if (!allowed[activeTab]) {
      setActiveTab(firstAvailableTab);
    }
  }, [
    activeTab,
    firstAvailableTab,
    canShowMovements,
    canShowLowStock,
    canShowOutOfStock,
    canShowReport,
  ]);

  // Handle URL parameters to open appropriate modals/tabs
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const action = params.get('action');
    const view = params.get('view');

    if (action === 'adjust' && canAdjust) {
      setShowAdjustmentModal(true);
      navigate('/inventory', { replace: true });
    } else if (action === 'transfer' && canTransfer) {
      setShowTransferModal(true);
      navigate('/inventory', { replace: true });
    } else if (view === 'movements' && canShowMovements) {
      setActiveTab('movements');
      navigate('/inventory', { replace: true });
    }
  }, [location.search, navigate, canAdjust, canTransfer, canShowMovements]);

  useEffect(() => {
    loadData();
  }, [filters, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'movements' && canShowMovements) {
        await loadMovements();
      } else if (activeTab === 'low_stock' && canShowLowStock) {
        await loadLowStock();
      } else if (activeTab === 'out_of_stock' && canShowOutOfStock) {
        await loadOutOfStock();
      } else if (activeTab === 'report' && canShowReport) {
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

  const handleBulkAdjust = () => {
    setShowBulkAdjustModal(true);
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

  const hasAnyTab =
    canShowMovements || canShowLowStock || canShowOutOfStock || canShowReport;

  if (loading && activeTab === 'movements' && movements.length === 0 && canShowMovements) {
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
          {canPurchase && (
            <Button onClick={handlePurchase}>
              <Plus className="h-4 w-4" />
              Record purchase
            </Button>
          )}
          {canAdjust && (
            <>
              <Button variant="outline" onClick={handleAdjustment}>
                <Scale className="h-4 w-4" />
                Adjust
              </Button>
              <Button variant="outline" onClick={handleBulkAdjust}>
                <Scale className="h-4 w-4" />
                Bulk adjust
              </Button>
            </>
          )}
          {canTransfer && (
            <Button variant="outline" onClick={handleTransfer}>
              <ArrowLeftRight className="h-4 w-4" />
              Transfer
            </Button>
          )}
        </PageHeader>

        {!hasAnyTab ? (
          <EmptyState
            icon={Package}
            title="Inventory views are hidden"
            description="Enable at least one inventory option under System Settings → Inventory / stock."
          />
        ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
            {canShowMovements && <TabsTrigger value="movements">Movements</TabsTrigger>}
            {canShowLowStock && (
              <TabsTrigger value="low_stock">
                Low stock ({lowStockProducts.length})
              </TabsTrigger>
            )}
            {canShowOutOfStock && (
              <TabsTrigger value="out_of_stock">
                Out of stock ({outOfStockProducts.length})
              </TabsTrigger>
            )}
            {canShowReport && <TabsTrigger value="report">Overview</TabsTrigger>}
          </TabsList>

          {canShowMovements && (
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
                actionLabel={canPurchase ? 'Record purchase' : undefined}
                onAction={canPurchase ? handlePurchase : undefined}
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
                        {canShowMovements && (
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
                        )}
                      </DataTableCell>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            )}
          </TabsContent>
          )}

          {canShowLowStock && (
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
                    canReorder={canPurchase}
                    onReorder={() => {
                      setSelectedProduct(product);
                      setShowPurchaseModal(true);
                    }}
                    onHistory={canShowMovements ? () => handleViewHistory(product) : undefined}
                  />
                ))}
              </div>
            )}
          </TabsContent>
          )}

          {canShowOutOfStock && (
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
                    canReorder={canPurchase}
                    onReorder={() => {
                      setSelectedProduct(product);
                      setShowPurchaseModal(true);
                    }}
                    onHistory={canShowMovements ? () => handleViewHistory(product) : undefined}
                  />
                ))}
              </div>
            )}
          </TabsContent>
          )}

          {canShowReport && (
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
          )}
        </Tabs>
        )}

      {showAdjustmentModal && canAdjust && (
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

      {showBulkAdjustModal && canAdjust && (
        <StockBulkAdjustModal
          onClose={() => setShowBulkAdjustModal(false)}
          onSave={() => {
            setShowBulkAdjustModal(false);
            loadData();
          }}
        />
      )}

      {showPurchaseModal && canPurchase && (
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

      {showHistoryModal && selectedProduct && canShowMovements && (
        <StockHistoryModal
          product={selectedProduct}
          showCost={showMovementCost}
          onClose={() => {
            setShowHistoryModal(false);
            setSelectedProduct(null);
          }}
        />
      )}

      {showTransferModal && canTransfer && (
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

function StockProductCard({ product, tone, label, canReorder = true, onReorder, onHistory }) {
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
          {canReorder && (
            <Button size="sm" onClick={onReorder}>
              Reorder
            </Button>
          )}
          {onHistory && (
            <Button size="sm" variant="outline" onClick={onHistory}>
              History
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default Inventory;
