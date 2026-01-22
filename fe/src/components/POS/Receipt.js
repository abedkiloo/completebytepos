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
                margin: 3mm;
              }
              @media print {
                @page {
                  size: auto;
                  margin: 3mm;
                }
                body {
                  width: 400px;
                  margin: 0 auto;
                }
                .receipt-wrapper {
                  width: 400px;
                  max-width: 400px;
                }
              }
              * {
                box-sizing: border-box;
              }
              body {
                font-family: 'Courier New', Courier, monospace;
                margin: 0;
                padding: 0;
                background: white;
                color: #111827;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                min-height: 100vh;
                font-size: 0.55rem;
                line-height: 1;
              }
              .receipt-wrapper {
                width: 400px;
                max-width: 400px;
                padding: 0.5rem;
                margin: 0 auto;
                line-height: 1;
                font-size: 0.55rem;
              }
              .receipt-cut-line {
                text-align: center;
                font-size: 0.7rem;
                color: #6b7280;
                margin-bottom: 0.3rem;
                padding-top: 0.2rem;
              }
              .receipt-header h3 {
                margin: 0 0 0.5rem 0;
                font-size: 1.0rem;
                color: #111827;
              }
              .receipt-company-name {
                text-align: center;
                font-size: 0.9rem;
                font-weight: bold;
                color: #111827;
                margin-bottom: 0.3rem;
              }
              .receipt-separator {
                text-align: center;
                font-size: 0.7rem;
                color: #111827;
                margin: 0.2rem 0;
                letter-spacing: 0.5px;
              }
              .receipt-info {
                margin-bottom: 0.5rem;
              }
              .receipt-info p {
                margin: 0.5rem 0;
                font-size: 0.7rem;
                color: #374151;
              }
              .receipt-transaction-details {
                margin: 0.3rem 0;
                font-size: 0.75rem;
              }
              .receipt-detail-row {
                display: flex;
                justify-content: space-between;
                margin: 0.15rem 0;
                color: #111827;
              }
              .receipt-detail-right {
                margin-left: auto;
              }
              .receipt-items-header {
                display: flex;
                justify-content: space-between;
                font-size: 0.75rem;
                font-weight: bold;
                margin: 0.2rem 0;
                color: #111827;
              }
              .receipt-items-header-left {
                text-align: left;
              }
              .receipt-items-header-right {
                text-align: right;
              }
              .receipt-items {
                margin: 0.2rem 0;
              }
              .receipt-items th,
              .receipt-items td {
                padding: 0.2rem;
                text-align: left;
                border-bottom: 0.3px solid #e5e7eb;
              }
              .receipt-items th {
                background: #f9fafb;
                font-weight: 600;
                font-size: 1rem;
                color: #374151;
              }
              .receipt-item-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 0.15rem 0;
                font-size: 0.75rem;
                color: #111827;
                white-space: nowrap;
                overflow: hidden;
              }
              .receipt-item-name {
                text-align: left;
                flex: 1;
                min-width: 0;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                margin-right: 0.5rem;
              }
              .receipt-item-amount {
                text-align: right;
                flex-shrink: 0;
                white-space: nowrap;
              }
              .receipt-summary {
                border-top: 1px solid #e5e7eb;
                padding-top: 0.2rem;
                margin-bottom: 0.2rem;
              }
              .summary-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.1rem 0;
                margin-bottom: 0.1rem;
                color: #374151;
                font-size: 0.9rem;
              }
              .summary-row.total {
                font-weight: 600;
                font-size: 0.5rem;
                margin-top: 0.3rem;
                padding-top: 0.3rem;
                border-top: 1px solid #e5e7eb;
                color: #111827;
              }
              .summary-row.total span {
                font-weight: 700;
                font-size: 0.9rem;
              }
              .summary-row.discount {
                color: #111827;
                font-weight: normal;
              }
              .receipt-vat-header {
                display: flex;
                justify-content: space-between;
                font-size: 0.7rem;
                font-weight: bold;
                margin: 0.2rem 0;
                color: #111827;
                padding: 0.1rem 0;
              }
              .receipt-vat-row {
                display: flex;
                justify-content: space-between;
                font-size: 0.7rem;
                color: #111827;
                margin: 0.15rem 0;
              }
              .vat-col {
                flex: 1;
                text-align: left;
              }
              .vat-col:first-child {
                flex: 0.5;
              }
              .receipt-footer {
                text-align: left;
                margin-top: 0.3rem;
                padding-top: 0.2rem;
                font-size: 0.75rem;
                color: #111827;
                border-top: none;
              }
              .thank-you {
                font-size: 0.75rem;
                font-weight: normal;
                color: #111827;
                margin: 0.3rem 0;
                text-align: left;
              }
              .receipt-identifiers {
                text-align: center;
                margin-top: 0.3rem;
                font-size: 0.7rem;
                color: #111827;
              }
              .receipt-id-line {
                margin: 0.1rem 0;
                font-family: 'Courier New', Courier, monospace;
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
        {/* Cut Line Indicator */}
        <div className="receipt-cut-line">---- CUT (100%) ----</div>
        
        {/* Company Name */}
        <div className="receipt-company-name">
          {sale.branch?.tenant?.name || sale.branch?.name || 'CompleteByte POS'}
        </div>
        
        {/* Dashed Separator */}
        <div className="receipt-separator">------------</div>
        
        {/* Transaction Details */}
        <div className="receipt-transaction-details">
          <div className="receipt-detail-row">
            <span>Slip: {sale.sale_number || 'N/A'}</span>
          </div>
          <div className="receipt-detail-row">
            <span>Staff: {sale.cashier_name || 'N/A'}</span>
            <span className="receipt-detail-right">Trans: {sale.id || (sale.sale_number ? sale.sale_number.split('-').pop() : 'N/A')}</span>
          </div>
          <div className="receipt-detail-row">
            <span>Date: {(() => {
              const d = new Date(sale.created_at);
              const day = String(d.getDate()).padStart(2, '0');
              const month = String(d.getMonth() + 1).padStart(2, '0');
              const year = String(d.getFullYear()).slice(-2);
              const hours = d.getHours();
              const minutes = String(d.getMinutes()).padStart(2, '0');
              return `${day}/${month}/${year} ${hours}:${minutes}`;
            })()}</span>
          </div>
        </div>
        
        {/* Dashed Separator */}
        <div className="receipt-separator">------------</div>
        
        {/* Itemized List Header */}
        <div className="receipt-items-header">
          <span className="receipt-items-header-left">Description</span>
          <span className="receipt-items-header-right">Amount</span>
        </div>
        
        {/* Dashed Separator */}
        <div className="receipt-separator">------------</div>
        
        {/* Receipt Items */}
        <div className="receipt-items">
          {sale.items && sale.items.map((item, index) => {
            const itemName = item.product_name || item.product?.name || 'N/A';
            const variantInfo = [];
            if (item.size_name) variantInfo.push(item.size_name);
            if (item.color_name) variantInfo.push(item.color_name);
            const variantStr = variantInfo.length > 0 ? ` ${variantInfo.join(' ')}` : '';
            const itemDisplay = `${itemName}${variantStr} pcs`;
            const amount = parseFloat(item.subtotal).toFixed(2);
            
            return (
              <div key={item.id || index} className="receipt-item-row">
                <span className="receipt-item-name">{itemDisplay}</span>
                <span className="receipt-item-amount">{amount} C</span>
              </div>
            );
          })}
        </div>
        
        {/* Dashed Separator */}
        <div className="receipt-separator">------------</div>
        
        {/* Receipt Summary */}
        <div className="receipt-summary">
          <div className="summary-row">
            <span>Subtotal LCY</span>
            <span>{parseFloat(sale.subtotal).toFixed(2)}</span>
          </div>
          {sale.discount_amount > 0 && (
            <div className="summary-row discount">
              <span>Discount - {sale.discount_amount > 0 && sale.subtotal > 0 ? Math.round((sale.discount_amount / sale.subtotal) * 100) : 0}%</span>
              <span>-{parseFloat(sale.discount_amount).toFixed(2)}</span>
            </div>
          )}
          <div className="summary-row total">
            <span>Total LCY</span>
            <span>{parseFloat(sale.total).toFixed(2)}</span>
          </div>
          {sale.amount_paid > 0 && (
            <div className="summary-row">
              <span>Cash</span>
              <span>-{parseFloat(sale.amount_paid).toFixed(2)}</span>
            </div>
          )}
        </div>
        
        {/* Dashed Separator */}
        <div className="receipt-separator">------------</div>
        
        {/* VAT Breakdown */}
        {sale.tax_amount > 0 && (
          <>
            <div className="receipt-vat-header">
              <span className="vat-col">VAT%</span>
              <span className="vat-col">Net.Amt</span>
              <span className="vat-col">VAT</span>
              <span className="vat-col">Amount</span>
            </div>
            <div className="receipt-vat-row">
              <span className="vat-col">C</span>
              <span className="vat-col">{(() => {
                const netAmount = parseFloat(sale.total) - parseFloat(sale.tax_amount);
                const taxRate = netAmount > 0 ? Math.round((parseFloat(sale.tax_amount) / netAmount) * 100) : 0;
                return taxRate;
              })()}</span>
              <span className="vat-col">{(parseFloat(sale.total) - parseFloat(sale.tax_amount)).toFixed(2)}</span>
              <span className="vat-col">{parseFloat(sale.tax_amount).toFixed(2)}</span>
              <span className="vat-col">{parseFloat(sale.total).toFixed(2)}</span>
            </div>
            <div className="receipt-separator">------------</div>
          </>
        )}

        {/* Receipt Footer */}
        <div className="receipt-footer">
          <p className="thank-you">Welcome again</p>
          <div className="receipt-identifiers">
            <div className="receipt-id-line">#{sale.id || sale.sale_number?.replace(/[^0-9]/g, '') || 'N/A'}</div>
            <div className="receipt-id-line">{`{${sale.sale_number || 'N/A'}`}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Receipt;

