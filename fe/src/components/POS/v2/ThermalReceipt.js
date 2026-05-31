import React, { forwardRef } from 'react';
import { formatCurrency } from '../../../utils/formatters';

/**
 * Thermal-printer-friendly receipt body.
 *
 * Layout follows standard retail receipt convention:
 *
 *   STORE NAME (centred, bold)
 *   address / phone / VAT id
 *   ================
 *   Receipt #SOM-001
 *   Date · Cashier · Customer
 *   ----------------
 *   Item name
 *     qty × unit ............ line total
 *   Item name
 *     qty × unit ............ line total
 *   ----------------
 *   Subtotal ........... 1234.00
 *   Discount ..........  -100.00
 *   VAT 16% ............  192.00
 *   ================
 *   TOTAL ............. 1326.00
 *   ================
 *   Cash ............... 1500.00
 *   Change .............  174.00
 *   ----------------
 *   Thank you message
 *   #sale-number (machine-readable footer)
 *
 * Width is 72mm of printable area (the 80mm thermal standard with 4mm of
 * gutter on each side). On screen we render slightly wider for legibility.
 *
 * This component is presentational only — it never reads from localStorage,
 * never fires API calls, never owns state. That's deliberate: the same JSX
 * has to render identically inside a Dialog AND inside a print iframe, so it
 * cannot depend on browser-only state or React Router.
 */
export const ThermalReceipt = forwardRef(function ThermalReceipt(
  { sale, store },
  ref
) {
  if (!sale) return null;

  const items = sale.items || [];
  const dateLabel = formatReceiptDate(sale.created_at);
  const cashierLabel = sale.cashier_name || sale.cashier || '';
  const balance = (parseFloat(sale.total) || 0) - (parseFloat(sale.amount_paid) || 0);
  const change = parseFloat(sale.change) || 0;
  const isPaymentMpesa = sale.payment_method === 'mpesa';
  const isPaymentCash = sale.payment_method === 'cash';
  const isPaymentWallet = sale.payment_method === 'wallet';
  const paymentLabel = friendlyPaymentLabel(sale.payment_method);

  return (
    <article
      ref={ref}
      className="receipt-thermal"
      data-receipt-root="true"
      aria-label={`Receipt ${sale.sale_number || ''}`}
    >
      {/* Header */}
      <header className="receipt-thermal__header">
        {store.receiptLogoUrl && (
          <img
            src={store.receiptLogoUrl}
            alt=""
            className="receipt-thermal__logo mx-auto mb-1 max-h-12 object-contain"
          />
        )}
        <div className="receipt-thermal__store">{store.storeName}</div>
        {store.receiptHeader && (
          <div className="receipt-thermal__line-thin">{store.receiptHeader}</div>
        )}
        {store.branchName && (
          <div className="receipt-thermal__branch">{store.branchName}</div>
        )}
        {store.address && (
          <div className="receipt-thermal__line-thin">{store.address}</div>
        )}
        {(store.phone || store.email) && (
          <div className="receipt-thermal__line-thin">
            {[store.phone, store.email].filter(Boolean).join(' · ')}
          </div>
        )}
        {store.taxId && (
          <div className="receipt-thermal__line-thin">PIN: {store.taxId}</div>
        )}
      </header>

      <DoubleRule />

      {/* Meta block */}
      <section className="receipt-thermal__meta">
        <ReceiptRow left="Receipt" right={sale.sale_number || '—'} bold />
        <ReceiptRow left="Date" right={dateLabel} />
        {cashierLabel && <ReceiptRow left="Cashier" right={cashierLabel} />}
      </section>

      <SingleRule />

      {/* Items */}
      <section className="receipt-thermal__items">
        {items.length === 0 ? (
          <div className="receipt-thermal__line-thin">No items.</div>
        ) : (
          items.map((item, index) => (
            <ReceiptItem
              key={item.id ?? index}
              item={item}
              showSku={store.showSku}
            />
          ))
        )}
      </section>

      <SingleRule />

      {/* Money breakdown */}
      <section className="receipt-thermal__totals">
        <ReceiptRow
          left="Subtotal"
          right={formatCurrency(sale.subtotal)}
          price
        />
        {!!parseFloat(sale.discount_amount) && (
          <ReceiptRow
            left="Discount"
            right={`-${formatCurrency(sale.discount_amount)}`}
            price
          />
        )}
        {!!parseFloat(sale.tax_amount) && (
          <ReceiptRow
            left={`VAT${sale.tax_rate ? ` (${sale.tax_rate}%)` : ''}`}
            right={formatCurrency(sale.tax_amount)}
            price
          />
        )}
        {!!parseFloat(sale.delivery_cost) && (
          <ReceiptRow
            left="Delivery"
            right={formatCurrency(sale.delivery_cost)}
            price
          />
        )}
      </section>

      <DoubleRule />

      <ReceiptRow
        left="TOTAL"
        right={formatCurrency(sale.total)}
        bold
        emphasised
        price
      />

      <DoubleRule />

      {/* Payment */}
      <section className="receipt-thermal__payment">
        <ReceiptRow
          left={paymentLabel}
          right={formatCurrency(sale.amount_paid)}
          price
        />
        {(isPaymentCash || isPaymentMpesa) && change > 0 && (
          <ReceiptRow left="Change" right={formatCurrency(change)} bold price />
        )}
        {balance > 0.005 && (
          <ReceiptRow
            left="Balance (owed)"
            right={formatCurrency(balance)}
            bold
            price
          />
        )}
        {isPaymentWallet && (
          <div className="receipt-thermal__note">
            Paid from customer wallet.
          </div>
        )}
      </section>

      <SingleRule />

      <footer className="receipt-thermal__footer">
        <p className="receipt-thermal__thanks">{store.receiptFooter}</p>
        <p className="receipt-thermal__sale-no">{sale.sale_number || ''}</p>
      </footer>
    </article>
  );
});

function ReceiptItem({ item, showSku = false }) {
  const name = item.product_name || item.product?.name || 'Item';
  const sku = item.product_sku || item.variant_sku || item.product?.sku || '';
  const variantParts = [item.size_name, item.color_name].filter(Boolean);
  const qty = parseFloat(item.quantity) || 0;
  const unit = parseFloat(item.unit_price) || 0;
  const subtotal = item.subtotal !== undefined
    ? parseFloat(item.subtotal)
    : qty * unit;

  return (
    <div className="receipt-thermal__item">
      <div className="receipt-thermal__item-name">
        {name}
        {variantParts.length > 0 && (
          <span className="receipt-thermal__item-variant">
            {' '}({variantParts.join(' · ')})
          </span>
        )}
      </div>
      {showSku && sku && (
        <div className="receipt-thermal__item-sku">{sku}</div>
      )}
      <ReceiptRow
        left={`  ${qty} × ${formatCurrency(unit)}`}
        right={formatCurrency(subtotal)}
        price
      />
    </div>
  );
}

function ReceiptRow({ left, right, bold = false, emphasised = false, price = false }) {
  const className = [
    'receipt-thermal__row',
    bold && 'receipt-thermal__row--bold',
    emphasised && 'receipt-thermal__row--emphasised',
  ].filter(Boolean).join(' ');
  const rightClass = [
    'receipt-thermal__row-right',
    price && 'receipt-thermal__row-right--price',
  ].filter(Boolean).join(' ');
  return (
    <div className={className}>
      <span className="receipt-thermal__row-left">{left}</span>
      <span className={rightClass}>{right}</span>
    </div>
  );
}

function DoubleRule() {
  return <div className="receipt-thermal__rule receipt-thermal__rule--double" aria-hidden="true" />;
}

function SingleRule() {
  return <div className="receipt-thermal__rule" aria-hidden="true" />;
}

function friendlyPaymentLabel(method) {
  switch (method) {
    case 'cash': return 'Cash';
    case 'mpesa': return 'M-Pesa';
    case 'wallet': return 'Wallet';
    case 'card': return 'Card';
    case 'bank_transfer': return 'Bank Transfer';
    default: return 'Paid';
  }
}

function formatReceiptDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  const day = pad(d.getDate());
  const month = pad(d.getMonth() + 1);
  const year = d.getFullYear();
  const hh = pad(d.getHours());
  const mm = pad(d.getMinutes());
  return `${day}/${month}/${year} ${hh}:${mm}`;
}

/**
 * The receipt's own CSS — kept inline so we can serialise it into the print
 * iframe alongside the markup. The on-screen Dialog imports it via the
 * adjacent css file; the print iframe gets the same rules as a <style> tag.
 *
 * Keep this string in lockstep with ./ThermalReceipt.css.
 */
export const THERMAL_RECEIPT_CSS = String.raw`
.receipt-thermal {
  width: 80mm;
  max-width: 80mm;
  padding: 4mm 4mm 6mm;
  margin: 0 auto;
  background: #ffffff;
  color: #000000;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 11pt;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}
.receipt-thermal__header {
  text-align: center;
  margin-bottom: 2mm;
}
.receipt-thermal__store {
  font-size: 14pt;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.receipt-thermal__branch {
  font-size: 10pt;
  font-weight: 600;
}
.receipt-thermal__line-thin {
  font-size: 9.5pt;
  margin-top: 0.5mm;
}
.receipt-thermal__rule {
  margin: 1.5mm 0;
  border-top: 1px dashed #000;
}
.receipt-thermal__rule--double {
  border-top: 1px solid #000;
  border-bottom: 1px solid #000;
  height: 0;
  padding: 0;
}
.receipt-thermal__meta,
.receipt-thermal__items,
.receipt-thermal__totals,
.receipt-thermal__payment {
  display: flex;
  flex-direction: column;
  gap: 0.5mm;
}
.receipt-thermal__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 4mm;
}
.receipt-thermal__row-left {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.receipt-thermal__row-right {
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.receipt-thermal__row-right--price {
  color: #15803d;
  font-weight: 700;
}
.receipt-thermal__row--bold .receipt-thermal__row-left,
.receipt-thermal__row--bold .receipt-thermal__row-right {
  font-weight: 700;
}
.receipt-thermal__row--emphasised {
  font-size: 13pt;
  padding: 0.5mm 0;
}
.receipt-thermal__row--emphasised .receipt-thermal__row-right--price {
  font-size: 14pt;
  font-weight: 800;
}
.receipt-thermal__item {
  padding: 0.5mm 0;
}
.receipt-thermal__item-name {
  font-weight: 600;
  word-break: break-word;
}
.receipt-thermal__item-sku {
  font-size: 9pt;
  font-family: ui-monospace, monospace;
  opacity: 0.65;
  margin-top: 0.25mm;
}
.receipt-thermal__item-variant {
  font-weight: 400;
  font-size: 10pt;
  opacity: 0.75;
}
.receipt-thermal__note {
  font-size: 9.5pt;
  font-style: italic;
  text-align: center;
  margin-top: 1mm;
}
.receipt-thermal__footer {
  text-align: center;
  margin-top: 2mm;
}
.receipt-thermal__thanks {
  margin: 0 0 1mm;
  font-weight: 600;
}
.receipt-thermal__sale-no {
  margin: 0;
  font-size: 9.5pt;
  letter-spacing: 1px;
}

/* Compact preset for 58mm thermal printers (some Kenyan retailers use these). */
.receipt-thermal--58mm {
  width: 58mm;
  max-width: 58mm;
  padding: 3mm;
  font-size: 9.5pt;
}
.receipt-thermal--58mm .receipt-thermal__store {
  font-size: 12pt;
}
.receipt-thermal--58mm .receipt-thermal__row--emphasised {
  font-size: 11pt;
}
`;
