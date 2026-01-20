import React, { useEffect } from 'react';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import './Receipt.css';

const Receipt = ({ sale, onClose }) => {
  // Set document title to sale number
  useEffect(() => {
    if (sale && sale.sale_number) {
      const originalTitle = document.title;
      document.title = `Receipt - ${sale.sale_number}`;
      
      return () => {
        document.title = originalTitle;
      };
    }
  }, [sale?.sale_number]);

  if (!sale) return null;

  const handlePrint = () => {
    // Ensure receipt content is visible before printing
    const receiptContent = document.getElementById('receipt-content');
    if (receiptContent) {
      // Create a new window for printing
      const printWindow = window.open('', '_blank');
      const printContent = receiptContent.innerHTML;
      
      printWindow.document.write(`
        <!DOCTYPE html>
        <html>
          <head>
            <title>Receipt - ${sale.sale_number}</title>
            <style>
              @page {
                size: auto;
                margin: 10mm;
              }
              body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                margin: 0;
                padding: 0;
                background: white;
                color: #111827;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                min-height: 100vh;
              }
              .receipt-wrapper {
                width: 400px;
                max-width: 400px;
                padding: 1.5rem;
                margin: 0 auto;
              }
              .receipt-header {
                text-align: center;
                border-bottom: 2px dashed #e5e7eb;
                padding-bottom: 1rem;
                margin-bottom: 1rem;
              }
              .receipt-logo {
                display: flex;
                justify-content: center;
                align-items: center;
                margin-bottom: 0.75rem;
              }
              .receipt-logo-img {
                max-width: 180px;
                height: auto;
                max-height: 50px;
              }
              .receipt-title {
                font-size: 1.5rem;
                font-weight: bold;
                color: #111827;
                margin: 0 0 0.25rem 0;
                text-transform: uppercase;
              }
              .receipt-subtitle {
                font-size: 0.875rem;
                color: #6b7280;
                margin: 0 0 1rem 0;
              }
              .receipt-info {
                text-align: left;
                font-size: 0.75rem;
                color: #374151;
              }
              .receipt-info p {
                margin: 0.25rem 0;
              }
              .receipt-info strong {
                color: #111827;
              }
              .receipt-items {
                margin: 1rem 0;
              }
              .receipt-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.85rem;
                table-layout: fixed;
              }
              .receipt-table thead {
                border-bottom: 2px solid #e5e7eb;
              }
              .receipt-table th {
                padding: 0.6rem 0.5rem;
                text-align: left;
                font-weight: 700;
                color: #111827;
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
              }
              .receipt-table th:first-child {
                width: 45%;
                padding-left: 0;
              }
              .receipt-table th:nth-child(2) {
                width: 12%;
                text-align: center;
              }
              .receipt-table th:nth-child(3),
              .receipt-table th:nth-child(4) {
                width: 21.5%;
                text-align: right;
                padding-right: 0;
              }
              .receipt-table td {
                padding: 0.6rem 0.5rem;
                color: #374151;
                border-bottom: 1px dotted #e5e7eb;
                vertical-align: top;
                word-wrap: break-word;
                overflow-wrap: break-word;
              }
              .receipt-table td:first-child {
                padding-left: 0;
              }
              .receipt-table td:nth-child(2) {
                text-align: center;
              }
              .receipt-table td:nth-child(3),
              .receipt-table td:nth-child(4) {
                text-align: right;
                padding-right: 0;
              }
              .item-name {
                font-weight: 500;
                color: #111827;
                font-size: 0.85rem;
                line-height: 1.4;
              }
              .item-sku {
                font-size: 0.7rem;
                color: #6b7280;
                font-weight: normal;
                display: block;
                margin-top: 0.2rem;
              }
              .receipt-summary {
                margin-top: 1.25rem;
                padding-top: 1rem;
                border-top: 2px dashed #e5e7eb;
                font-size: 0.9rem;
              }
              .summary-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.55rem 0;
                color: #374151;
                line-height: 1.5;
              }
              .summary-row span:first-child {
                font-weight: 500;
              }
              .summary-row span:last-child {
                font-weight: 600;
                text-align: right;
                min-width: 120px;
              }
              .summary-row.discount {
                color: #10b981;
              }
              .summary-row.total {
                border-top: 2px solid #e5e7eb;
                margin-top: 0.75rem;
                padding-top: 0.85rem;
                font-size: 1.05rem;
                color: #111827;
              }
              .summary-row.total span {
                font-weight: 700;
                font-size: 1.1rem;
              }
              .summary-row.change {
                color: #667eea;
                font-weight: 600;
                font-size: 1rem;
                margin-top: 0.5rem;
              }
              .summary-row.balance-due {
                color: #ef4444;
                font-weight: 600;
              }
              .payment-method {
                text-transform: uppercase;
                font-weight: 600;
                color: #667eea;
                letter-spacing: 0.5px;
              }
              .receipt-footer {
                text-align: center;
                margin-top: 1.5rem;
                padding-top: 1rem;
                border-top: 2px dashed #e5e7eb;
              }
              .thank-you {
                font-size: 1rem;
                font-weight: 600;
                color: #111827;
                margin: 0.5rem 0;
              }
              .footer-text {
                font-size: 0.875rem;
                color: #6b7280;
                margin: 0.25rem 0;
              }
            </style>
          </head>
          <body>
            <div class="receipt-wrapper">
              ${printContent}
            </div>
          </body>
        </html>
      `);
      
      printWindow.document.close();
      
      // Wait for content to load, then print
      setTimeout(() => {
        printWindow.focus();
        printWindow.print();
        // Close the print window after printing
        setTimeout(() => {
          printWindow.close();
        }, 250);
      }, 250);
    } else {
      // Fallback to regular print
      window.print();
    }
  };

  return (
    <div className="receipt-container">
      <div className="receipt-actions">
        <button onClick={handlePrint} className="btn-print">Print Receipt</button>
        <button onClick={onClose} className="btn-close">Close</button>
      </div>
      
      <div className="receipt-content" id="receipt-content">
        {/* Receipt Header */}
        <div className="receipt-header">
          <div className="receipt-logo">
            <img src="/logo.svg" alt="CompleteByte POS" className="receipt-logo-img" />
          </div>
          <p className="receipt-location">HQ</p>
          <p className="receipt-address">Nairobi, Kenya</p>
        </div>

        {/* Receipt Items */}
        <div className="receipt-items">
          <table className="receipt-table">
            <thead>
              <tr>
                <th>Item</th>
                <th className="text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {sale.items && sale.items.map((item, index) => {
                // Format item name with quantity and price: "Product Name (Qty@Price)"
                const itemName = item.product_name || item.product?.name || 'N/A';
                const variantInfo = [];
                if (item.size_name) variantInfo.push(item.size_name);
                if (item.color_name) variantInfo.push(item.color_name);
                const variantStr = variantInfo.length > 0 ? ` ${variantInfo.join('/')}` : '';
                const itemDisplay = `${itemName}${variantStr} (${item.quantity}@${parseFloat(item.unit_price).toFixed(2)})`;
                
                return (
                  <tr key={item.id || index}>
                    <td className="item-name">{itemDisplay}</td>
                    <td className="text-right">{parseFloat(item.subtotal).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Receipt Summary */}
        <div className="receipt-summary">
          <div className="summary-row">
            <span>Subtotal</span>
            <span>{parseFloat(sale.subtotal).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
          </div>
          {sale.discount_amount > 0 && (
            <div className="summary-row discount">
              <span>Discount</span>
              <span>-{parseFloat(sale.discount_amount).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          )}
          {sale.tax_amount > 0 && (
            <div className="summary-row">
              <span>Tax</span>
              <span>{parseFloat(sale.tax_amount).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          )}
          <div className="summary-row total">
            <span>Total</span>
            <span>Ksh{formatCurrency(sale.total).replace('KES', '').trim()}</span>
          </div>
          {sale.amount_paid > 0 && (
            <div className="summary-row">
              <span>Amount Paid</span>
              <span>Ksh{parseFloat(sale.amount_paid).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          )}
          {sale.change > 0 && (
            <div className="summary-row change">
              <span>Change</span>
              <span>Ksh{parseFloat(sale.change).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          )}
          {(!sale.change || sale.change === 0) && sale.amount_paid < sale.total && (
            <div className="summary-row balance-due">
              <span>Balance Due</span>
              <span>Ksh{parseFloat(sale.total - (sale.amount_paid || 0)).toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          )}
        </div>

        {/* Shipping Information */}
        {(sale.shipping_address || sale.shipping_location) && (
          <div className="receipt-shipping" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px dashed #e5e7eb' }}>
            <p style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.9rem' }}>Shipping Information</p>
            {sale.delivery_method && (
              <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                <strong>Method:</strong> {sale.delivery_method.charAt(0).toUpperCase() + sale.delivery_method.slice(1)}
              </p>
            )}
            {sale.shipping_address && (
              <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                <strong>Address:</strong> {sale.shipping_address}
              </p>
            )}
            {sale.shipping_location && (
              <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                <strong>Location:</strong> {sale.shipping_location}
              </p>
            )}
            {sale.delivery_cost > 0 && (
              <p style={{ fontSize: '0.85rem', margin: '0.25rem 0' }}>
                <strong>Delivery Cost:</strong> {formatCurrency(sale.delivery_cost)}
              </p>
            )}
          </div>
        )}

        {/* Receipt Footer */}
        <div className="receipt-footer">
          {sale.cashier_name && (
            <p className="footer-info">Served by: {sale.cashier_name}</p>
          )}
          <p className="footer-info">Sale#: {sale.sale_number}</p>
          <p className="footer-info">Date: {formatDateTime(sale.created_at)}</p>
          <p className="thank-you">Thanks! See you soon.</p>
          <p className="footer-powered">Powered by CompleteByte POS</p>
          <p className="footer-contact">Contact us: +254 700 000 000</p>
        </div>
      </div>
    </div>
  );
};

export default Receipt;

