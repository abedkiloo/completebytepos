import React from 'react';
import { render, screen } from '@testing-library/react';
import ApprovalDetails, { formatApprovalQty } from './ApprovalDetails';
import { expenseApprovalDetails } from '../../utils/approvalDisplay';

describe('ApprovalDetails', () => {
  it('renders facts, items, and money', () => {
    render(
      <ApprovalDetails
        details={{
          sections: [
            {
              title: 'Sale',
              facts: [
                { label: 'Customer', value: 'Mama Duka', kind: 'text' },
                { label: 'Sale date', value: '2026-10-01T09:30:00+03:00', kind: 'datetime' },
              ],
            },
            {
              title: 'Items',
              lines: [
                {
                  name: 'Blue Kitenge',
                  variant: 'L / Blue',
                  quantity: '2',
                  unit_price: '250.00',
                  subtotal: '500.00',
                },
              ],
            },
            { title: 'Money', facts: [{ label: 'Total', value: '500.00', kind: 'money' }] },
          ],
        }}
      />
    );
    expect(screen.getByText('Mama Duka')).toBeInTheDocument();
    expect(screen.getByText('Blue Kitenge')).toBeInTheDocument();
    expect(screen.getByText('L / Blue')).toBeInTheDocument();
    expect(screen.getByText('Unit price')).toBeInTheDocument();
    expect(screen.getAllByText(/500/).length).toBeGreaterThanOrEqual(2);
  });

  it('shows plain qty instead of scientific notation', () => {
    render(
      <ApprovalDetails
        details={{
          sections: [
            {
              title: 'Items',
              lines: [
                {
                  name: 'Sofa pins',
                  quantity: '1E+1',
                  unit_price: '430.00',
                  subtotal: '4300.00',
                },
              ],
            },
          ],
        }}
      />
    );
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.queryByText('1E+1')).not.toBeInTheDocument();
  });

  it('formats scientific qty strings', () => {
    expect(formatApprovalQty('1E+1')).toBe('10');
    expect(formatApprovalQty(10)).toBe('10');
    expect(formatApprovalQty('2.5')).toBe('2.5');
  });

  it('renders nothing without sections', () => {
    const { container } = render(<ApprovalDetails details={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('builds expense details from the expense row', () => {
    const details = expenseApprovalDetails({
      expense_number: 'EXP-1',
      amount: '1200.00',
      category_name: 'Rent',
      expense_date: '2026-10-01',
      payment_method: 'mpesa',
      vendor: '',
    });
    const labels = details.sections[0].facts.map((fact) => fact.label);
    expect(labels).toEqual(['Reference', 'Amount', 'Category', 'Expense date', 'Payment method']);
    expect(details.sections[0].facts[4].value).toBe('M-PESA');
  });
});
