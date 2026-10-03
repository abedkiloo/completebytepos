import React from 'react';
import { render, screen } from '@testing-library/react';
import ApprovalDetails from './ApprovalDetails';
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
