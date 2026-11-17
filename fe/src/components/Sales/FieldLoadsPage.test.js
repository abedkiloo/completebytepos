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
    approveIssue: jest.fn(),
    declineIssue: jest.fn(),
    reviseIssue: jest.fn(),
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
    localStorage.removeItem('enabled_modules');
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: false, can_approve: true, results: [pending] },
    });
    fieldLoadsAPI.accept.mockResolvedValue({ data: { ...pending, status: 'accepted' } });
    fieldLoadsAPI.sell.mockResolvedValue({ data: openLoad });
    customersAPI.list.mockResolvedValue({ data: { results: [{ id: 3, name: 'Field Duka' }] } });
  });

  test('turning the field loads feature off hides the screen', () => {
    localStorage.setItem('enabled_modules', JSON.stringify({
      sales: { is_enabled: true, features: { field_load: { is_enabled: false } } },
    }));
    render(<FieldLoadsPage />);
    expect(screen.getByText(/Field loads are turned off/)).toBeInTheDocument();
    expect(screen.queryByText('Create new field load')).not.toBeInTheDocument();
  });

  test('a manager can accept a counted load and an agent does not see issue controls', async () => {
    render(<FieldLoadsPage />);
    expect((await screen.findAllByText('Asha')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Submit for approval' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve reconciliation' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Approve reconciliation' }));
    await waitFor(() => expect(fieldLoadsAPI.accept).toHaveBeenCalledWith(7, {}));
  });

  test('a manager approves the quantities a sales person wrote', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: {
        can_issue: false,
        can_approve: true,
        results: [{
          ...pending,
          status: 'awaiting_issue',
          display_status: 'awaiting_issue',
          can_confirm_issue: true,
          issued_by: 'Asha',
        }],
      },
    });
    fieldLoadsAPI.approveIssue.mockResolvedValue({
      data: { ...pending, status: 'open', display_status: 'open', can_confirm_issue: false },
    });
    render(<FieldLoadsPage />);
    expect(await screen.findByRole('button', { name: /Asha/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve quantities' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    expect(screen.queryByRole('button', { name: 'Create new field load' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Approve quantities' }));
    await waitFor(() => expect(fieldLoadsAPI.approveIssue).toHaveBeenCalledWith(7));
  });

  test('recording a sale posts the product, quantity, customer, and amount', async () => {
    const withLegs = {
      ...openLoad,
      lines: [
        ...openLoad.lines,
        {
          id: 2,
          product_id: 5,
          product_name: 'Legs',
          quantity_taken: 10,
          quantity_sold: 0,
          quantity_returned: null,
          quantity_missing: null,
        },
      ],
    };
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [withLegs] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({ data: { results: [{ id: 2, name: 'Asha' }] } });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /Asha/ }));
    expect(await screen.findByRole('button', { name: /Legs/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Submit for approval' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create new field load' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Cups/ }));
    expect(screen.queryByText('Legs')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record a field load sale' })).toBeInTheDocument();
    expect(screen.getByText(/does not create a field order/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Back to stock' }));
    expect(screen.getByRole('button', { name: /Legs/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Cups/ }));
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

  test('a sales person sees their own name and cannot pick someone else', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({
      data: { choose_employee: false, results: [{ id: 4, name: 'Mercy Mercy' }] },
    });
    render(<FieldLoadsPage />);
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Create new field load' }));
    expect(await screen.findByDisplayValue('Mercy Mercy')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Sales employee' })).not.toBeInTheDocument();
  });

  test('product search updates as the name is typed and the chosen quantity is added', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({ data: { results: [{ id: 2, name: 'Asha' }] } });
    productsAPI.search.mockResolvedValue({
      data: [
        { id: 9, name: 'Sofa Cup', sku: 'CUP-GOLD-01', stock_quantity: 120 },
        { id: 10, name: 'Sofa Legs', sku: 'LEG-01', stock_quantity: 15 },
      ],
    });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Create new field load' }));
    const box = await screen.findByLabelText('Find product');
    await userEvent.type(box, 'cup');
    await waitFor(() => expect(productsAPI.search).toHaveBeenCalledWith('cup', 20));
    expect(await screen.findByRole('button', { name: /Sofa Legs/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Sofa Cup/ }));
    expect(screen.queryByRole('button', { name: /Sofa Legs/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Available: 120 pieces/)).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText('Quantity of Sofa Cup'));
    await userEvent.type(screen.getByLabelText('Quantity of Sofa Cup'), '40');
    await userEvent.click(screen.getByRole('button', { name: 'Add to load' }));
    expect(screen.getByText('Total product quantities')).toBeInTheDocument();
    expect(screen.getByText('40')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Remove Sofa Cup' }));
    expect(screen.getByText('No products on this draft yet.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove Sofa Cup' })).not.toBeInTheDocument();
    expect(screen.queryByText('Sofa Cup')).not.toBeInTheDocument();
  });

  test('each tab shows only its loads, and an approval opens on its own', async () => {
    const selling = {
      ...openLoad,
      id: 8,
      agent_name: 'John',
      reference: 'FL-2026-00002',
    };
    fieldLoadsAPI.list.mockResolvedValue({
      data: {
        can_issue: true,
        can_approve: true,
        results: [
          { ...pending, status: 'awaiting_issue', display_status: 'awaiting_issue', can_confirm_issue: true, reference: 'FL-2026-00001' },
          selling,
        ],
      },
    });
    render(<FieldLoadsPage />);
    expect(await screen.findByRole('button', { name: /Asha/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /John/ })).toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Awaiting approval$/ }));
    expect(screen.getByRole('button', { name: /Asha/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /John/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    expect(screen.getByRole('button', { name: 'Approve quantities' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create new field load' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();
    expect(screen.queryByText('Available stock')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /John/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Back to loads' }));
    await userEvent.click(screen.getByRole('button', { name: /^Open$/ }));
    expect(screen.getByRole('button', { name: /John/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Asha/ })).not.toBeInTheDocument();
  });

  test('the person who wrote a sent-back load can change it and send it again', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: {
        can_issue: true,
        can_approve: false,
        results: [{
          ...pending,
          status: 'issue_rejected',
          display_status: 'issue_rejected',
          can_revise_issue: true,
          review_note: 'Take fewer cups',
          reference: 'FL-2026-00001',
        }],
      },
    });
    fieldLoadsAPI.reviseIssue.mockResolvedValue({
      data: { ...pending, status: 'awaiting_issue', can_revise_issue: false },
    });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /^Awaiting approval$/ }));
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    expect(screen.getByText('Take fewer cups')).toBeInTheDocument();
    expect(screen.getByText('Cups')).toBeInTheDocument();
    const qty = screen.getByLabelText('Quantity of Cups');
    await userEvent.clear(qty);
    await userEvent.type(qty, '2');
    await userEvent.click(screen.getByRole('button', { name: 'Send again for approval' }));
    await waitFor(() => expect(fieldLoadsAPI.reviseIssue).toHaveBeenCalledWith(7, {
      lines: [{ product_id: 4, quantity: 2 }],
    }));
    expect(screen.queryByRole('button', { name: 'Send again for approval' })).not.toBeInTheDocument();
  });
});
