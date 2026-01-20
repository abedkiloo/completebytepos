import React, { useState, useEffect, useCallback } from 'react';
import { salesAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import { toast } from '../../utils/toast';
import './Sales.css';

const Sales = () => {
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSale, setSelectedSale] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
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

  const getStatusBadgeClass = (sale) => {
    // Status can be determined by payment method or other criteria
    return 'completed'; // Default status
  };

  return (
    <Layout>
      <div className="sales-page">
        <div className="page-header">
          <div>
            <h1>Sales History</h1>
            <p>Manage and view all sales transactions</p>
          </div>
        </div>

        {/* Filters */}
        <div className="sales-filters">
          <div className="filter-group">
            <label>From Date</label>
            <input
              type="date"
              name="date_from"
              value={filters.date_from}
              onChange={handleFilterChange}
            />
          </div>
          <div className="filter-group">
            <label>To Date</label>
            <input
              type="date"
              name="date_to"
              value={filters.date_to}
              onChange={handleFilterChange}
            />
          </div>
          <div className="filter-group">
            <label>Payment Method</label>
            <select
              name="payment_method"
              value={filters.payment_method}
              onChange={handleFilterChange}
            >
              <option value="">All Methods</option>
              <option value="cash">Cash</option>
              <option value="mpesa">M-PESA</option>
              <option value="card">Card</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Search</label>
            <input
              type="text"
              name="search"
              placeholder="Search by sale number..."
              value={filters.search}
              onChange={handleFilterChange}
            />
          </div>
        </div>

        {/* Sales Table */}
        <div className="sales-table-container">
          {loading ? (
            <div className="loading-state">Loading sales...</div>
          ) : sales.length === 0 ? (
            <div className="empty-state">No sales found</div>
          ) : (
            <>
              <table className="sales-table">
                <thead>
                  <tr>
                    <th>Sale Number</th>
                    <th>Date</th>
                    <th>Cashier</th>
                    <th>Items</th>
                    <th>Subtotal</th>
                    <th>Tax</th>
                    <th>Discount</th>
                    <th>Total</th>
                    <th>Payment</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map(sale => (
                    <tr key={sale.id}>
                      <td>
                        <button
                          className="sale-number-link"
                          onClick={() => handleViewReceipt(sale)}
                          title="Click to view sale details"
                        >
                          {sale.sale_number}
                        </button>
                      </td>
                      <td>{formatDateTime(sale.created_at)}</td>
                      <td>{sale.cashier_name || 'N/A'}</td>
                      <td>{sale.item_count || 0}</td>
                      <td>{formatCurrency(sale.subtotal)}</td>
                      <td>{formatCurrency(sale.tax_amount)}</td>
                      <td>{formatCurrency(sale.discount_amount)}</td>
                      <td className="total-amount">{formatCurrency(sale.total)}</td>
                      <td>
                        <span className="payment-badge">{sale.payment_method}</span>
                      </td>
                      <td>
                        <span className={`status-badge ${getStatusBadgeClass(sale)}`}>
                          Completed
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn-view"
                          onClick={() => handleViewReceipt(sale)}
                        >
                          View Receipt
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {pagination.count > pagination.page_size && (
                <div className="pagination">
                  <button
                    disabled={pagination.page === 1}
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                  >
                    Previous
                  </button>
                  <span>
                    Page {pagination.page} of {Math.ceil(pagination.count / pagination.page_size)}
                  </span>
                  <button
                    disabled={pagination.page >= Math.ceil(pagination.count / pagination.page_size)}
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Receipt Modal */}
        {showReceiptModal && selectedSale && (
          <div className="modal-overlay" onClick={() => setShowReceiptModal(false)}>
            <div className="modal-content receipt-modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Receipt - {selectedSale.sale_number}</h2>
                <button className="modal-close" onClick={() => setShowReceiptModal(false)}>×</button>
              </div>
              <div className="receipt-content">
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
                              {item.variant_sku && (
                                <div style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>
                                  SKU: {item.variant_sku}
                                </div>
                              )}
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
              <div className="modal-footer">
                <button onClick={handlePrintReceipt}>Print Receipt</button>
                <button onClick={() => setShowReceiptModal(false)}>Close</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Sales;
