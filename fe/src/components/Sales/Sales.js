import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Receipt, RotateCcw, ShoppingCart, Clock } from 'lucide-react';
import { salesAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import { getStoredAuth, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { userCanRefundSales, saleIsRefundable, handleSaleRefundResponse } from '../../utils/saleRefund';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { saleDisplayItemCount, saleDisplayTotal } from '../../utils/saleItemDisplay';
import RefundSaleDialog from './RefundSaleDialog';
import SaleDetailDialog from './SaleDetailDialog';
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

const Sales = () => {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const { permissions } = getStoredAuth();
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    payment_method: '',
    search: '',
  });
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });

  const loadSales = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: pagination.page,
        page_size: pagination.page_size,
      };
      
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.payment_method) params.payment_method = filters.payment_method;
      if (filters.search) params.search = filters.search;
      
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
  }, [filters, pagination.page, pagination.page_size]);

  useEffect(() => {
    loadSales();
  }, [loadSales]);

  const handleViewReceipt = async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setSelectedSale(response.data);
      setShowReceiptModal(true);
    } catch (error) {
      toast.error('Failed to load receipt: ' + (error.response?.data?.error || error.message));
    }
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

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

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
        
        // Wait for content to load, then print
        setTimeout(() => {
          printWindow.focus();
          printWindow.print();
          // Restore original title
          document.title = originalTitle;
          // Close the print window after printing
          setTimeout(() => {
            printWindow.close();
          }, 250);
        }, 250);
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
              ? 'Review transactions, reprint receipts, or void mistaken sales. A full void refunds stock, reverses books, and clears customer account balances.'
              : 'Review completed transactions and reprint receipts.'
          }
        >
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
                { id: 'card', name: 'Card' },
                { id: 'other', name: 'Other' },
              ]}
              placeholder="All methods"
            />
          </FilterField>
          <FilterField label="Search" className="min-w-[200px] flex-[2]">
            <Input
              type="search"
              name="search"
              placeholder="Sale number…"
              value={filters.search}
              onChange={handleFilterChange}
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
            onPageChange={(nextPage) =>
              setPagination((prev) => ({ ...prev, page: nextPage }))
            }
          >
            <DataTable>
              <DataTableHeader>
                <DataTableHead>Sale #</DataTableHead>
                <DataTableHead>Date</DataTableHead>
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
                        className="font-medium text-primary hover:underline"
                        onClick={() => handleViewReceipt(sale)}
                      >
                        {sale.sale_number}
                      </button>
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
                      <StatusBadge status={sale.status || 'completed'} />
                    </DataTableCell>
                    <DataTableCell align="right">
                      <div className="flex justify-end gap-1">
                        {canRefund && saleIsRefundable(sale) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            onClick={() => openRefundDialog(sale)}
                          >
                            <RotateCcw className="mr-1 h-3.5 w-3.5" />
                            Void / Refund
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewReceipt(sale)}
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
          onRefund={(sale) => {
            setShowReceiptModal(false);
            openRefundDialog(sale);
          }}
          onPrint={handlePrintReceipt}
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
      </PageShell>
  );
};

export default Sales;
