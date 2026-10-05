import { Badge } from '../ui/badge';

export function isFieldSale(sale) {
  if (!sale) return false;
  return Boolean(
    sale.is_field_sale || sale.sale_origin === 'field' || sale.entry_source === 'field'
  );
}

export function saleOriginLabel(sale) {
  return isFieldSale(sale) ? 'Field sale' : 'Shop sale';
}

/** Tells field sales (from packed field orders) apart from sales made in the shop. */
export default function SaleOriginBadge({ sale, className = '' }) {
  const field = isFieldSale(sale);
  return (
    <Badge
      variant={field ? 'warning' : 'outline'}
      className={`text-[10px] whitespace-nowrap ${className}`.trim()}
      data-testid="sale-origin"
    >
      {saleOriginLabel(sale)}
    </Badge>
  );
}
