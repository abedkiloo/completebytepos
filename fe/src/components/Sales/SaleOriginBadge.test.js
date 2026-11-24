/**
 * Sale origin badge: shop vs field order vs field load.
 */
import { render, screen } from '@testing-library/react';
import SaleOriginBadge, {
  isFieldLoadSale,
  isFieldSale,
  saleOriginLabel,
} from './SaleOriginBadge';

describe('SaleOriginBadge', () => {
  test('unit: field_load origin is not a packed field sale', () => {
    const sale = { sale_origin: 'field_load', entry_source: 'field_load' };
    expect(isFieldLoadSale(sale)).toBe(true);
    expect(isFieldSale(sale)).toBe(false);
    expect(saleOriginLabel(sale)).toBe('Field load');
  });

  test('unit: packed field order stays Field sale', () => {
    const sale = { sale_origin: 'field', is_field_sale: true };
    expect(isFieldSale(sale)).toBe(true);
    expect(isFieldLoadSale(sale)).toBe(false);
    expect(saleOriginLabel(sale)).toBe('Field sale');
  });

  test('unit: shop sale default', () => {
    expect(saleOriginLabel({ sale_origin: 'shop' })).toBe('Shop sale');
    expect(saleOriginLabel(null)).toBe('Shop sale');
  });

  test('integration: badge renders Field load with data-origin', () => {
    render(<SaleOriginBadge sale={{ entry_source: 'field_load' }} />);
    const badge = screen.getByTestId('sale-origin');
    expect(badge).toHaveTextContent('Field load');
    expect(badge).toHaveAttribute('data-origin', 'field_load');
  });

  test('corrected functionality: is_field_load_sale wins over is_field_sale', () => {
    const sale = {
      is_field_load_sale: true,
      is_field_sale: true,
      sale_origin: 'field',
    };
    expect(isFieldLoadSale(sale)).toBe(true);
    expect(isFieldSale(sale)).toBe(false);
    expect(saleOriginLabel(sale)).toBe('Field load');
  });

  test('stress: many origin rows stay labeled', () => {
    const rows = Array.from({ length: 200 }, (_, i) => {
      if (i % 3 === 0) return { sale_origin: 'field_load' };
      if (i % 3 === 1) return { sale_origin: 'field' };
      return { sale_origin: 'shop' };
    });
    const labels = rows.map(saleOriginLabel);
    expect(labels.filter((l) => l === 'Field load').length).toBeGreaterThan(60);
    expect(labels.filter((l) => l === 'Field sale').length).toBeGreaterThan(60);
    expect(labels.filter((l) => l === 'Shop sale').length).toBeGreaterThan(60);
  });

  test('security: badge does not echo phone or notes from sale payload', () => {
    render(
      <SaleOriginBadge
        sale={{
          sale_origin: 'field_load',
          customer_phone: '0712345678',
          notes: 'call 0712345678',
        }}
      />
    );
    expect(screen.getByTestId('sale-origin')).toHaveTextContent('Field load');
    expect(screen.queryByText(/0712345678/)).toBeNull();
  });
});
