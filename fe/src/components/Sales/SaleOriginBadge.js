import { Badge } from '../ui/badge';

/**
 * True when the sale came from a packed field order (not a field load bag).
 *
 * @param {object|null|undefined} sale Sale row from the API.
 * @returns {boolean}
 */
export function isFieldSale(sale) {
  if (!sale) return false;
  if (isFieldLoadSale(sale)) return false;
  return Boolean(
    sale.is_field_sale || sale.sale_origin === 'field' || sale.entry_source === 'field'
  );
}

/**
 * True when the sale used stock already on an approved field load.
 *
 * @param {object|null|undefined} sale Sale row from the API.
 * @returns {boolean}
 */
export function isFieldLoadSale(sale) {
  if (!sale) return false;
  return Boolean(
    sale.is_field_load_sale
      || sale.sale_origin === 'field_load'
      || sale.entry_source === 'field_load'
  );
}

/**
 * Short label for shop, field-order, or field-load origin.
 *
 * @param {object|null|undefined} sale Sale row from the API.
 * @returns {'Field load'|'Field sale'|'Shop sale'}
 */
export function saleOriginLabel(sale) {
  if (isFieldLoadSale(sale)) return 'Field load';
  return isFieldSale(sale) ? 'Field sale' : 'Shop sale';
}

/**
 * Tells shop POS, packed field orders, and field-load bag sales apart.
 *
 * @param {{ sale?: object|null, className?: string }} props
 * @returns {JSX.Element}
 */
export default function SaleOriginBadge({ sale, className = '' }) {
  const load = isFieldLoadSale(sale);
  const field = !load && isFieldSale(sale);
  const variant = load ? 'secondary' : field ? 'warning' : 'outline';
  return (
    <Badge
      variant={variant}
      className={`text-[10px] whitespace-nowrap ${className}`.trim()}
      data-testid="sale-origin"
      data-origin={load ? 'field_load' : field ? 'field' : 'shop'}
    >
      {saleOriginLabel(sale)}
    </Badge>
  );
}
