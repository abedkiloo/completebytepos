import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Receipt, RotateCcw, ShoppingCart } from 'lucide-react';
import { salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import { getStoredAuth, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { userCanRefundSales, saleIsRefundable, refundStatusLabel } from '../../utils/saleRefund';
import RefundSaleDialog from './RefundSaleDialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
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
    page_size: 20,
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
      console.error('Error loading sales:', error);
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
      const response = await salesAPI.receipt(sale.id);
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
      toast.success(`Refund ${res.data.refund_number} recorded`);
      setRefundSale(null);
      if (selectedSale?.id === refundSale.id) {
        setShowReceiptModal(false);
        setSelectedSale(null);
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

  const totalPages = Math.ceil(pagination.count / pagination.page_size) || 1;

  if (loading && sales.length === 0) {
    return (
      <PageLoading rows={8} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="Sales history"
          description="Review completed transactions and reprint receipts."
        >
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
          <>
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
                {sales.map((sale) => (
                  <DataTableRow key={sale.id}>
                    <DataTableCell>
                      <button
                        type="button"
                        className="font-medium text-primary hover:underline"
                        onClick={() => handleViewReceipt(sale)}
                      >
                        {sale.sale_number}
                      </button>
                    </DataTableCell>
                    <DataTableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDateTime(sale.created_at)}
                    </DataTableCell>
                    <DataTableCell>{sale.cashier_name || '—'}</DataTableCell>
                    <DataTableCell align="right">{sale.item_count || 0}</DataTableCell>
                    <DataTableCell align="right" className="font-semibold">
                      {formatCurrency(sale.total)}
                    </DataTableCell>
                    <DataTableCell>
                      <Badge variant="outline" className="capitalize">
                        {sale.payment_method}
                      </Badge>
                    </DataTableCell>
                    <DataTableCell>
                      <div className="flex flex-col gap-1">
                        <StatusBadge status={sale.status || 'completed'} />
                        {refundStatusLabel(sale.refund_status) && (
                          <Badge variant="secondary" className="w-fit text-xs">
                            {refundStatusLabel(sale.refund_status)}
                          </Badge>
                        )}
                      </div>
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
                            Refund
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
                ))}
              </DataTableBody>
            </DataTable>

            {pagination.count > pagination.page_size && (
              <div className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Page {pagination.page} of {totalPages} · {pagination.count} sales
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.page === 1}
                    onClick={() =>
                      setPagination((prev) => ({ ...prev, page: prev.page - 1 }))
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pagination.page >= totalPages}
                    onClick={() =>
                      setPagination((prev) => ({ ...prev, page: prev.page + 1 }))
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}

        <Dialog open={showReceiptModal} onOpenChange={setShowReceiptModal}>
          <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Receipt — {selectedSale?.sale_number}</DialogTitle>
            </DialogHeader>
            {selectedSale && (
              <div className="receipt-content space-y-4 text-sm">
                <div className="receipt-header">
                  <h3>CompleteByte POS</h3>
                  <p>Sale Receipt</p>
                </div>
                <div className="receipt-info">
                  <p><strong>Sale Number:</strong> {selectedSale.sale_number}</p>
                  <p><strong>Date:</strong> {formatDateTime(selectedSale.created_at)}</p>
                  <p><strong>Cashier:</strong> {selectedSale.cashier_name || 'N/A'}</p>
                </div>
                <div className="receipt-items">
                  <table>
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        <th>Price</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedSale.items?.map((item, idx) => {
                        const itemName = item.product_name || item.product?.name || 'N/A';
                        const variantInfo = [];
                        if (item.size_name) variantInfo.push(`Size: ${item.size_name}`);
                        if (item.color_name) variantInfo.push(`Color: ${item.color_name}`);
                        const variantStr = variantInfo.length > 0 ? ` (${variantInfo.join(', ')})` : '';
                        const displayName = `${itemName}${variantStr}`;
                        
                        return (
                          <tr key={idx}>
                            <td>
                              <div>{displayName}</div>
                            </td>
                            <td>{item.quantity}</td>
                            <td>{formatCurrency(item.unit_price)}</td>
                            <td>{formatCurrency(item.subtotal)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="receipt-summary">
                  <div className="summary-row">
                    <span>Subtotal:</span>
                    <span>{formatCurrency(selectedSale.subtotal)}</span>
                  </div>
                  {selectedSale.tax_amount > 0 && (
                    <div className="summary-row">
                      <span>Tax:</span>
                      <span>{formatCurrency(selectedSale.tax_amount)}</span>
                    </div>
                  )}
                  {selectedSale.discount_amount > 0 && (
                    <div className="summary-row">
                      <span>Discount:</span>
                      <span>-{formatCurrency(selectedSale.discount_amount)}</span>
                    </div>
                  )}
                  <div className="summary-row total">
                    <span>Total:</span>
                    <span>{formatCurrency(selectedSale.total)}</span>
                  </div>
                  <div className="summary-row">
                    <span>Payment Method:</span>
                    <span>{selectedSale.payment_method}</span>
                  </div>
                  <div className="summary-row">
                    <span>Amount Paid:</span>
                    <span>{formatCurrency(selectedSale.amount_paid)}</span>
                  </div>
                  {selectedSale.change > 0 && (
                    <div className="summary-row">
                      <span>Change:</span>
                      <span>{formatCurrency(selectedSale.change)}</span>
                    </div>
                  )}
                </div>
                {/* Shipping Information */}
                {(selectedSale.shipping_address || selectedSale.shipping_location) && (
                  <div className="receipt-shipping" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px dashed #e5e7eb' }}>
                    <p style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.9rem' }}>Shipping Information</p>
                    {selectedSale.delivery_method && (
                      <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                        <strong>Method:</strong> {selectedSale.delivery_method.charAt(0).toUpperCase() + selectedSale.delivery_method.slice(1)}
                      </p>
                    )}
                    {selectedSale.shipping_address && (
                      <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                        <strong>Address:</strong> {selectedSale.shipping_address}
                      </p>
                    )}
                    {selectedSale.shipping_location && (
                      <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                        <strong>Location:</strong> {selectedSale.shipping_location}
                      </p>
                    )}
                    {selectedSale.delivery_cost > 0 && (
                      <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                        <strong>Delivery Cost:</strong> {formatCurrency(selectedSale.delivery_cost)}
                      </p>
                    )}
                  </div>
                )}
                {selectedSale.notes && (
                  <div className="receipt-notes">
                    <p><strong>Notes:</strong> {selectedSale.notes}</p>
                  </div>
                )}
                <div className="receipt-footer">
                  <p>Thank you for your business!</p>
                </div>
              </div>
            )}
            <DialogFooter className="flex-wrap gap-2 sm:justify-between">
              <div>
                {canRefund && selectedSale && saleIsRefundable(selectedSale) && (
                  <Button
                    variant="destructive"
                    onClick={() => {
                      setShowReceiptModal(false);
                      openRefundDialog(selectedSale);
                    }}
                  >
                    <RotateCcw className="mr-1 h-4 w-4" />
                    Refund
                  </Button>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setShowReceiptModal(false)}>
                  Close
                </Button>
                <Button onClick={handlePrintReceipt}>Print receipt</Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>

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
