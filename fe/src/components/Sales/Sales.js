import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, Receipt, RotateCcw, ShoppingCart, Clock } from 'lucide-react';
import { salesAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { toast } from '../../utils/toast';
import {
  getStoredAuth,
  isManagerOrAdminFromStorage,
  userSeesAllSalesFromStorage,
} from '../../utils/roleAccess';
import { useSellerOptions } from '../../hooks/useSellerOptions';
import { canViewDailySalesFromStorage } from '../../utils/dailySalesAccess';
import { userCanRefundSales, saleIsRefundable, handleSaleRefundResponse, userCanRollbackSales, saleIsRollbackable } from '../../utils/saleRefund';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { DEFAULT_BRAND_LOGO } from '../../utils/storeBranding';
import {
  SALE_AWAITING_APPROVAL_MESSAGE,
  saleIsAwaitingApproval,
  saleNeedsSalespersonAction,
  saleReceiptBlockedReason,
  userHasAdminSaleOverride,
} from '../../utils/saleCompletionApproval';
import { saleDisplayItemCount, saleDisplayTotal, saleFinalStatusLabel, saleStatusBadgeTone } from '../../utils/saleItemDisplay';
import RefundSaleDialog from './RefundSaleDialog';
import SaleRollbackDialog from './SaleRollbackDialog';
import SaleDetailDialog from './SaleDetailDialog';
import SaleChannelIcon from './SaleChannelIcon';
import SaleOriginBadge from './SaleOriginBadge';
import HelpHint from '../Shared/HelpHint';
import CenterScreenLoader from '../Shared/CenterScreenLoader';
import ReportExportButtons from '../Reports/ReportExportButtons';
import { salesHistoryExportParams } from '../../utils/reportExport';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
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
  StatusBadge,
  ListPaginationRail,
} from '../page';
import { useListOrdering } from '../../hooks/useListOrdering';
import { withListOrdering } from '../../utils/listOrdering';

const Sales = () => {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [rollbackSale, setRollbackSale] = useState(null);
  const [rollbackSubmitting, setRollbackSubmitting] = useState(false);
  const { permissions } = getStoredAuth();
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const canRollback = userCanRollbackSales(permissions);
  const canReturnForCorrection = userHasAdminSaleOverride();
  const canViewDaily = canViewDailySalesFromStorage();
  const canFilterBySeller = userSeesAllSalesFromStorage();
  const sellerOptions = useSellerOptions(canFilterBySeller);
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    payment_method: '',
    search: '',
    cashier_id: '',
  });
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebouncedValue(searchInput, 300);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });
  const { ordering, setOrdering } = useListOrdering();
  const [historyTab, setHistoryTab] = useState('completed');

  useEffect(() => {
    setFilters((prev) => {
      if (prev.search === debouncedSearch) return prev;
      return { ...prev, search: debouncedSearch };
    });
  }, [debouncedSearch]);

  useEffect(() => {
    setPagination((p) => (p.page === 1 ? p : { ...p, page: 1 }));
  }, [filters.search]);

  const loadSales = useCallback(async () => {
    setLoading(true);
    try {
      const params = withListOrdering({
        page: pagination.page,
        page_size: pagination.page_size,
      }, ordering);
      
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.payment_method) params.payment_method = filters.payment_method;
      if (filters.search) params.search = filters.search;
      if (filters.cashier_id) params.cashier_id = filters.cashier_id;
      if (historyTab === 'pending') params.status = 'pending_approval';
      const response = await salesAPI.list(params);
      const data = response.data;
      
      if (data.results) {
        setSales(data.results);
        setPagination(prev => ({
          ...prev,
          count: data.count || 0,
        }));
      } else {
        setSales(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      setSales([]);
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.page_size, historyTab, ordering]);

  useEffect(() => {
    loadSales();
  }, [loadSales]);

  const handleViewSale = async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setSelectedSale(response.data);
      setShowReceiptModal(true);
    } catch (error) {
      toast.error('Failed to load sale: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleViewReceipt = async (sale) => {
    const blocked = saleReceiptBlockedReason(sale);
    if (blocked) {
      toast.info(blocked);
      return;
    }
    await handleViewSale(sale);
  };

  const openRefundDialog = async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setRefundSale(response.data);
    } catch (error) {
      toast.error('Failed to load sale: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleRefundSubmit = async (payload) => {
    if (!refundSale) return;
    setRefundSubmitting(true);
    try {
      const res = await salesAPI.refund(refundSale.id, payload);
      const outcome = handleSaleRefundResponse(res, {
        onApplied: (data) => toast.success(`Void recorded as ${data.refund_number}`),
        onPending: () => toast.success(pendingApprovalToastMessage()),
      });
      setRefundSale(null);
      if (outcome === 'applied' && selectedSale?.id === refundSale.id) {
        const refreshed = await salesAPI.get(refundSale.id);
        setSelectedSale(refreshed.data);
      }
      loadSales();
    } catch (error) {
      const data = error.response?.data;
      const msg =
        data?.reason?.[0] ||
        data?.items?.[0] ||
        data?.error ||
        data?.detail ||
        error.message;
      toast.error(typeof msg === 'string' ? msg : 'Refund failed');
    } finally {
      setRefundSubmitting(false);
    }
  };

  const openRollbackDialog = async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setRollbackSale(response.data);
    } catch (error) {
      toast.error('Failed to load sale: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleRollbackSubmit = async (payload) => {
    if (!rollbackSale) return;
    setRollbackSubmitting(true);
    try {
      const res = await salesAPI.rollback(rollbackSale.id, payload);
      handleSaleRefundResponse(res, {
        onApplied: (data) => toast.success(`Sale rolled back as ${data.refund_number}`),
        onPending: () => toast.success(pendingApprovalToastMessage()),
      });
      setRollbackSale(null);
      if (selectedSale?.id === rollbackSale.id) {
        const refreshed = await salesAPI.get(rollbackSale.id);
        setSelectedSale(refreshed.data);
      }
      loadSales();
    } catch (error) {
      const data = error.response?.data;
      const msg = data?.reason?.[0] || data?.error || data?.detail || error.message;
      toast.error(typeof msg === 'string' ? msg : 'Rollback failed');
    } finally {
      setRollbackSubmitting(false);
    }
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const exportParams = salesHistoryExportParams(filters);

  const handlePrintReceipt = () => {
    if (selectedSale) {
      // Set document title
      const originalTitle = document.title;
      document.title = `Receipt - ${selectedSale.sale_number}`;
      
      // Get receipt content
      const receiptContent = document.querySelector('.receipt-content');
      if (receiptContent) {
        // Create a new window for printing
        const printWindow = window.open('', '_blank');
        const printContent = receiptContent.innerHTML;
        
        printWindow.document.write(`
          <!DOCTYPE html>
          <html>
            <head>
              <title>Receipt - ${selectedSale.sale_number}</title>
              <style>
                @page {
                  size: auto;
                  margin: 10mm;
                }
                body {
                  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                  margin: 0;
                  padding: 1rem;
                  background: white;
                  color: #111827;
                }
                .receipt-header {
                  text-align: center;
                  margin-bottom: 1.5rem;
                  padding-bottom: 1rem;
                  border-bottom: 2px solid #e5e7eb;
                }
                .receipt-header img {
                  display: block;
                  height: 64px;
                  width: 64px;
                  margin: 0 auto 0.5rem;
                  object-fit: contain;
                }
                .receipt-header h3 {
                  margin: 0 0 0.5rem 0;
                  font-size: 1.5rem;
                  color: #111827;
                }
                .receipt-info {
                  margin-bottom: 1.5rem;
                }
                .receipt-info p {
                  margin: 0.5rem 0;
                  font-size: 0.9rem;
                  color: #374151;
                }
                .receipt-items {
                  margin-bottom: 1.5rem;
                }
                .receipt-items table {
                  width: 100%;
                  border-collapse: collapse;
                }
                .receipt-items th,
                .receipt-items td {
                  padding: 0.75rem;
                  text-align: left;
                  border-bottom: 1px solid #e5e7eb;
                }
                .receipt-items th {
                  background: #f9fafb;
                  font-weight: 600;
                  font-size: 0.875rem;
                  color: #374151;
                }
                .receipt-summary {
                  border-top: 2px solid #e5e7eb;
                  padding-top: 1rem;
                  margin-bottom: 1rem;
                }
                .summary-row {
                  display: flex;
                  justify-content: space-between;
                  margin-bottom: 0.5rem;
                  font-size: 0.9rem;
                }
                .summary-row.total {
                  font-weight: 600;
                  font-size: 1.1rem;
                  margin-top: 0.5rem;
                  padding-top: 0.5rem;
                  border-top: 1px solid #e5e7eb;
                }
                .receipt-footer {
                  text-align: center;
                  margin-top: 1.5rem;
                  padding-top: 1rem;
                  border-top: 1px solid #e5e7eb;
                  color: #6b7280;
                }
              </style>
            </head>
            <body>
              ${printContent}
            </body>
          </html>
        `);
        
        printWindow.document.close();

        const images = Array.from(printWindow.document.images || []);
        const imagesReady = Promise.all(
          images.map((img) =>
            img.complete
              ? null
              : new Promise((done) => {
                  img.onload = done;
                  img.onerror = () => {
                    img.src = DEFAULT_BRAND_LOGO;
                    done();
                  };
                })
          )
        );
        const timeout = new Promise((done) => setTimeout(done, 3000));
        Promise.race([imagesReady, timeout]).then(() => {
          printWindow.focus();
          printWindow.print();
          document.title = originalTitle;
          setTimeout(() => {
            printWindow.close();
          }, 250);
        });
      } else {
        window.print();
        // Restore original title after a delay
        setTimeout(() => {
          document.title = originalTitle;
        }, 1000);
      }
    }
  };

  if (loading && sales.length === 0) {
    return (
      <PageLoading rows={8} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Sales history"
          description={
            canRefund
              ? 'Review transactions, reprint receipts, or void mistaken sales. Download PDF or Excel for the current filters. Voiding a sale needs admin approval before stock and books change.'
              : 'Review completed transactions, reprint receipts, and download PDF or Excel for the current filters.'
          }
        >
          <ReportExportButtons slug="sales-history" params={exportParams} />
          {canViewDaily ? (
            <Button variant="outline" asChild>
              <Link to="/sales/daily">
                <Calendar className="h-4 w-4" />
                Daily sales
              </Link>
            </Button>
          ) : null}
          <Button variant="outline" asChild>
            <Link to="/sales/record-past">
              <Clock className="h-4 w-4" />
              Record past sale
            </Link>
          </Button>
          <Button asChild>
            <Link to="/pos">
              <ShoppingCart className="h-4 w-4" />
              Open POS
            </Link>
          </Button>
        </PageHeader>

        <div className="mb-3 flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={historyTab === 'completed' ? 'default' : 'outline'}
            onClick={() => {
              setHistoryTab('completed');
              setPagination((prev) => ({ ...prev, page: 1 }));
            }}
          >
            Completed
          </Button>
          <Button
            type="button"
            size="sm"
            variant={historyTab === 'pending' ? 'default' : 'outline'}
            onClick={() => {
              setHistoryTab('pending');
              setPagination((prev) => ({ ...prev, page: 1 }));
            }}
          >
            Awaiting approval
          </Button>
        </div>

        <FilterBar>
          <FilterField label="From">
            <Input
              type="date"
              name="date_from"
              value={filters.date_from}
              onChange={handleFilterChange}
            />
          </FilterField>
          <FilterField label="To">
            <Input
              type="date"
              name="date_to"
              value={filters.date_to}
              onChange={handleFilterChange}
            />
          </FilterField>
          <FilterField label="Payment">
            <SearchableSelect
              name="payment_method"
              value={filters.payment_method}
              onChange={handleFilterChange}
              options={[
                { id: '', name: 'All methods' },
                { id: 'cash', name: 'Cash' },
                { id: 'mpesa', name: 'M-PESA' },
              ]}
              placeholder="All methods"
            />
          </FilterField>
          {canFilterBySeller && (
            <FilterField label="Sold by">
              <SearchableSelect
                name="cashier_id"
                value={filters.cashier_id}
                onChange={handleFilterChange}
                options={[{ id: '', name: 'Everyone' }, ...sellerOptions]}
                placeholder="Everyone"
              />
            </FilterField>
          )}
          <FilterField label="Search" className="min-w-[12rem] flex-1 sm:min-w-[14rem]">
            <Input
              type="search"
              name="search"
              placeholder="Sale number, customer…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value || '')}
            />
          </FilterField>
        </FilterBar>

        {sales.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="No sales in this range"
            description="Try different dates or start selling from POS."
            actionLabel="Open POS"
            onAction={() => window.location.assign('/pos')}
          />
        ) : (
          <ListPaginationRail
            page={pagination.page}
            pageSize={pagination.page_size}
            totalCount={pagination.count}
            suffix={`${pagination.count} sales`}
            ordering={ordering}
            onOrderingChange={setOrdering}
            onPageChange={(nextPage) =>
              setPagination((prev) => ({ ...prev, page: nextPage }))
            }
          >
            <DataTable>
              <DataTableHeader>
                <DataTableHead>Sale #</DataTableHead>
                <DataTableHead sortKey="saved" ordering={ordering} onOrderingChange={setOrdering}>
                  Date
                </DataTableHead>
                <DataTableHead>Cashier</DataTableHead>
                <DataTableHead align="right">Items</DataTableHead>
                <DataTableHead align="right">Total</DataTableHead>
                <DataTableHead>Payment</DataTableHead>
                <DataTableHead>Status</DataTableHead>
                <DataTableHead align="right">Actions</DataTableHead>
              </DataTableHeader>
              <DataTableBody>
                {sales.map((sale) => {
                  const displayTotal = saleDisplayTotal(sale);
                  const itemCount = saleDisplayItemCount(sale);
                  const saleWhen = sale.occurred_at || sale.created_at;
                  return (
                  <DataTableRow key={sale.id}>
                    <DataTableCell>
                      <button
                        type="button"
                        className="font-medium text-primary hover:underline inline-flex items-center gap-1.5"
                        onClick={() => handleViewSale(sale)}
                      >
                        <SaleChannelIcon channel={sale.client_channel} />
                        {sale.sale_number}
                      </button>
                      <SaleOriginBadge sale={sale} className="ml-1" />
                      {sale.is_late_entry ? (
                        <Badge variant="outline" className="ml-1 text-[10px]">
                          Late entry
                        </Badge>
                      ) : null}
                    </DataTableCell>
                    <DataTableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDateTime(saleWhen)}
                    </DataTableCell>
                    <DataTableCell>{sale.cashier_name || '—'}</DataTableCell>
                    <DataTableCell align="right">{itemCount}</DataTableCell>
                    <DataTableCell align="right" className="font-semibold">
                      {formatCurrency(displayTotal)}
                    </DataTableCell>
                    <DataTableCell>
                      <Badge variant="outline" className="capitalize">
                        {sale.payment_method}
                      </Badge>
                    </DataTableCell>
                    <DataTableCell>
                      <StatusBadge
                        status={saleStatusBadgeTone(sale)}
                        label={saleFinalStatusLabel(sale)}
                      />
                      {saleNeedsSalespersonAction(sale) && sale.rejection_reason ? (
                        <p className="mt-1 max-w-[14rem] text-xs text-muted-foreground">
                          {sale.rejection_reason}
                        </p>
                      ) : null}
                    </DataTableCell>
                    <DataTableCell align="right">
                      <div className="flex justify-end gap-1">
                        {canRollback && saleIsRollbackable(sale) && (
                          <span className="inline-flex items-center">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => openRollbackDialog(sale)}
                            >
                              <RotateCcw className="mr-1 h-3.5 w-3.5" />
                              Roll back
                            </Button>
                            <HelpHint actionKey="sale_rollback" />
                          </span>
                        )}
                        {canRefund && saleIsRefundable(sale) && (
                          <span className="inline-flex items-center">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => openRefundDialog(sale)}
                            >
                              <RotateCcw className="mr-1 h-3.5 w-3.5" />
                              Void / refund
                            </Button>
                            <HelpHint actionKey="sale_refund" />
                          </span>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewReceipt(sale)}
                          disabled={
                            saleIsAwaitingApproval(sale) || saleNeedsSalespersonAction(sale)
                          }
                          title={
                            saleNeedsSalespersonAction(sale)
                              ? 'Fix this sale on POS and send it again before issuing a receipt.'
                              : saleIsAwaitingApproval(sale)
                              ? SALE_AWAITING_APPROVAL_MESSAGE
                              : undefined
                          }
                        >
                          Receipt
                        </Button>
                      </div>
                    </DataTableCell>
                  </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </ListPaginationRail>
        )}

        <SaleDetailDialog
          sale={selectedSale}
          open={showReceiptModal}
          onOpenChange={setShowReceiptModal}
          canRefund={canRefund}
          canRollback={canRollback}
          canReturnForCorrection={canReturnForCorrection}
          onReturned={() => {
            setShowReceiptModal(false);
            loadSales();
          }}
          onRefund={(sale) => {
            setShowReceiptModal(false);
            openRefundDialog(sale);
          }}
          onRollback={(sale) => {
            setShowReceiptModal(false);
            openRollbackDialog(sale);
          }}
          onPrint={handlePrintReceipt}
          onUpdated={(updated) => {
            setSelectedSale(updated);
            loadSales();
          }}
        />

        <RefundSaleDialog
          sale={refundSale}
          open={Boolean(refundSale)}
          onOpenChange={(open) => {
            if (!open) setRefundSale(null);
          }}
          onSubmit={handleRefundSubmit}
          submitting={refundSubmitting}
        />

        <SaleRollbackDialog
          sale={rollbackSale}
          open={Boolean(rollbackSale)}
          onOpenChange={(open) => {
            if (!open) setRollbackSale(null);
          }}
          onSubmit={handleRollbackSubmit}
          submitting={rollbackSubmitting}
        />

        <CenterScreenLoader
          open={refundSubmitting || rollbackSubmitting}
          label={
            refundSubmitting
              ? 'Submitting void…'
              : rollbackSubmitting
                ? 'Submitting rollback…'
                : 'Loading…'
          }
        />
      </PageShell>
  );
};

export default Sales;
