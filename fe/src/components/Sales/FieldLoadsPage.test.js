import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import FieldLoadsPage from './FieldLoadsPage';

jest.mock('../../services/api', () => ({
  fieldLoadsAPI: {
    list: jest.fn(),
    agents: jest.fn(),
    create: jest.fn(),
    sell: jest.fn(),
    returnCount: jest.fn(),
    accept: jest.fn(),
    reject: jest.fn(),
  },
  customersAPI: { list: jest.fn() },
  productsAPI: { search: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

const { fieldLoadsAPI, customersAPI, productsAPI } = require('../../services/api');

const pending = {
  id: 7,
  status: 'pending_review',
  agent_name: 'Asha',
  lines: [
    {
      id: 1,
      product_id: 4,
      product_name: 'Cups',
      quantity_taken: 40,
      quantity_sold: 15,
      quantity_returned: 20,
      quantity_missing: 5,
      still_out: 25,
    },
  ],
  money: { expected: '750.00', collected: '750.00' },
  sales: [],
};

const openLoad = {
  ...pending,
  status: 'open',
  lines: [{ ...pending.lines[0], quantity_returned: null, quantity_missing: null }],
};

describe('FieldLoadsPage', () => {
  beforeEach(() => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: false, can_approve: true, results: [pending] },
    });
    fieldLoadsAPI.accept.mockResolvedValue({ data: { ...pending, status: 'accepted' } });
    fieldLoadsAPI.sell.mockResolvedValue({ data: openLoad });
    customersAPI.list.mockResolvedValue({ data: { results: [{ id: 3, name: 'Field Duka' }] } });
  });

  test('a manager can accept a counted load and an agent does not see issue controls', async () => {
    render(<FieldLoadsPage />);
    expect((await screen.findAllByText('Asha')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Confirm and issue load' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Approve reconciliation' }));
    await waitFor(() => expect(fieldLoadsAPI.accept).toHaveBeenCalledWith(7, {}));
  });

  test('recording a sale posts the product, quantity, customer, and amount', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [openLoad] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({ data: { results: [{ id: 2, name: 'Asha' }] } });
    render(<FieldLoadsPage />);
    expect(await screen.findByRole('button', { name: 'Record a field load sale' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm and issue load' })).toBeInTheDocument();
    expect(screen.getByText(/does not create a field order/i)).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Field Duka' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Customer'), '3');
    await userEvent.clear(screen.getByLabelText('Amount received'));
    await userEvent.type(screen.getByLabelText('Amount received'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Record a field load sale' }));
    await waitFor(() => expect(fieldLoadsAPI.sell).toHaveBeenCalledWith(7, {
      product_id: 4,
      quantity: 1,
      customer_id: 3,
      amount_paid: '50',
      payment_method: 'cash',
      client_channel: 'web',
      notes: '',
    }));
    expect(screen.queryByRole('button', { name: 'Approve reconciliation' })).not.toBeInTheDocument();
  });

  test('product search updates as the name is typed and the chosen quantity is added', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({ data: { results: [{ id: 2, name: 'Asha' }] } });
    productsAPI.search.mockResolvedValue({
      data: [{ id: 9, name: 'Sofa Cup', sku: 'CUP-GOLD-01', stock_quantity: 120 }],
    });
    render(<FieldLoadsPage />);
    const box = await screen.findByLabelText('Find product');
    await userEvent.type(box, 'cup');
    await waitFor(() => expect(productsAPI.search).toHaveBeenCalledWith('cup', 20));
    await userEvent.click(await screen.findByRole('button', { name: /Sofa Cup/ }));
    expect(screen.getByText(/Available: 120 pieces/)).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText('Quantity of Sofa Cup'));
    await userEvent.type(screen.getByLabelText('Quantity of Sofa Cup'), '40');
    await userEvent.click(screen.getByRole('button', { name: '+ Add to load' }));
    expect(screen.getByText('Total product quantities')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
  });
});
