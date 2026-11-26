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

jest.mock('../../utils/moduleFeatures', () => ({
  isProductVariantsEnabled: () => true,
}));

jest.mock('../POS/VariantSelector', () => ({
  __esModule: true,
  default: function MockVariantSelector({ product, onSelect, onClose, initialQuantity }) {
    return (
      <div role="dialog" aria-label={`Choose variant for ${product?.name || 'product'}`}>
        <button
          type="button"
          onClick={() => onSelect({
            variant: {
              id: 55,
              stock_quantity: 20,
              size_name: 'L',
              color_name: 'Gold',
              sku: 'SHIRT-L-GOLD',
            },
            quantity: initialQuantity || 1,
          })}
        >
          Pick L / Gold
        </button>
        <button type="button" onClick={onClose}>Close variants</button>
      </div>
    );
  },
}));

const { fieldLoadsAPI, customersAPI, productsAPI } = require('../../services/api');

const pending = {
  id: 7,
  status: 'pending_review',
  agent_name: 'Asha',
  units_sold: 15,
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
  sales: [{ id: 9, sale_number: 'S-9', total: '750.00', customer_name: 'Field Duka', payment_method: 'cash' }],
};

const noSalesLoad = {
  id: 8,
  status: 'open',
  agent_name: 'Kamau',
  reference: 'FL-2026-8',
  units_sold: 0,
  lines: [
    {
      id: 2,
      product_id: 4,
      product_name: 'Cups',
      quantity_taken: 10,
      quantity_sold: 0,
      quantity_returned: null,
      quantity_missing: null,
      still_out: 10,
      unit_price: '50.00',
    },
  ],
  money: { expected: '0.00', collected: '0.00', cash: '0.00', mpesa: '0.00', credit: '0.00' },
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

  test('corrected: an open load with no sales says so on the list and detail', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [noSalesLoad] },
    });
    render(<FieldLoadsPage />);
    expect(await screen.findByText('No sales yet on this load.')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Kamau'));
    expect(await screen.findByTestId('field-load-no-sales')).toHaveTextContent(
      'No sales yet on this load.',
    );
    expect(screen.queryByTestId('field-load-sales-list')).not.toBeInTheDocument();
  });

  test('a manager can accept a counted load and an agent does not see issue controls', async () => {
    render(<FieldLoadsPage />);
    expect((await screen.findAllByText('Asha')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Submit for approval' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve reconciliation' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Asha/ }));
    expect(screen.getByTestId('field-load-send-back-return')).toBeInTheDocument();
    expect(screen.getByTestId('field-load-send-back-return').className).toMatch(/warning/);
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
        {
          ...openLoad.lines[0],
          unit_price: '50.00',
        },
        {
          id: 2,
          product_id: 5,
          product_name: 'Legs',
          quantity_taken: 10,
          quantity_sold: 0,
          quantity_returned: null,
          quantity_missing: null,
          unit_price: '50.00',
        },
      ],
    };
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [withLegs] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({ data: { results: [{ id: 2, name: 'Asha' }] } });
    customersAPI.list.mockResolvedValue({
      data: { results: [{ id: 3, name: 'Field Duka', phone: '0718000003' }] },
    });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /Asha/ }));
    expect(screen.getByText(/every product in this sale/i)).toBeInTheDocument();
    expect(screen.getByText('Legs')).toBeInTheDocument();
    expect(screen.getByText('Cups')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Debt' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Record a field load sale' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Quantity of Cups'), '1');
    await userEvent.type(screen.getByLabelText('Quantity of Legs'), '2');
    await userEvent.click(screen.getByText('Walk-in customer'));
    expect(await screen.findByText('Field Duka')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Field Duka'));
    await userEvent.clear(screen.getByLabelText('Amount received'));
    await userEvent.type(screen.getByLabelText('Amount received'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Record a field load sale' }));
    await waitFor(() => expect(fieldLoadsAPI.sell).toHaveBeenCalledWith(7, {
      lines: [
        { product_id: 4, quantity: 1 },
        { product_id: 5, quantity: 2 },
      ],
      customer_id: 3,
      amount_paid: '50',
      payment_method: 'cash',
      client_channel: 'web',
      notes: '',
    }));
  });

  test('corrected: debt sale requires a searchable customer and posts on account', async () => {
    const openCups = {
      ...openLoad,
      sales: [],
      units_sold: 0,
      lines: [{
        ...openLoad.lines[0],
        quantity_sold: 0,
        unit_price: '50.00',
      }],
    };
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: false, results: [openCups] },
    });
    customersAPI.list.mockResolvedValue({
      data: { results: [{ id: 3, name: 'Field Duka', phone: '0718000003' }] },
    });
    fieldLoadsAPI.sell.mockResolvedValue({ data: openCups });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /Asha/ }));
    await userEvent.type(screen.getByLabelText('Quantity of Cups'), '1');
    await userEvent.click(screen.getByRole('button', { name: 'Debt' }));
    expect(screen.getByText(/Debt puts the full sale/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Record a field load sale' }));
    expect(fieldLoadsAPI.sell).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText('Select customer'));
    expect(await screen.findByText('Field Duka')).toBeInTheDocument();
    await userEvent.click(screen.getByText('Field Duka'));
    await userEvent.click(screen.getByRole('button', { name: 'Record a field load sale' }));
    await waitFor(() => expect(fieldLoadsAPI.sell).toHaveBeenCalledWith(7, expect.objectContaining({
      customer_id: 3,
      amount_paid: 0,
      payment_method: 'debt',
    })));
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

  test('a manager chooses themselves or someone else and issues without approval', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: true, results: [] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({
      data: {
        choose_employee: true,
        results: [
          { id: 1, name: 'Asha Manager' },
          { id: 4, name: 'Mercy Mercy' },
        ],
      },
    });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Create new field load' }));
    const people = await screen.findByRole('combobox', { name: 'Person carrying this load' });
    expect(screen.getByRole('option', { name: 'Asha Manager' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Mercy Mercy' })).toBeInTheDocument();
    expect(screen.getByText(/does not wait for approval/)).toBeInTheDocument();
    await userEvent.selectOptions(people, '1');
    expect(screen.getByRole('button', { name: 'Issue load' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Submit for approval' })).not.toBeInTheDocument();
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

  test('corrected: issuing a variant product opens the picker and posts variant_id', async () => {
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: true, can_approve: true, results: [] },
    });
    fieldLoadsAPI.agents.mockResolvedValue({
      data: {
        choose_employee: true,
        results: [{ id: 1, name: 'Asha Manager' }],
      },
    });
    productsAPI.search.mockResolvedValue({
      data: [{
        id: 22,
        name: 'Field Shirt',
        sku: 'SHIRT',
        stock_quantity: 0,
        has_variants: true,
      }],
    });
    fieldLoadsAPI.create.mockResolvedValue({
      data: {
        id: 90,
        status: 'open',
        agent_name: 'Asha Manager',
        lines: [{
          id: 1,
          product_id: 22,
          variant_id: 55,
          product_name: 'Field Shirt · L / Gold',
          quantity_taken: 2,
          quantity_sold: 0,
          available: 2,
          unit_price: '50.00',
        }],
        money: { expected: '0.00', collected: '0.00' },
        sales: [],
      },
    });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Create new field load' }));
    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Person carrying this load' }),
      '1',
    );
    await userEvent.type(screen.getByLabelText('Find product'), 'shirt');
    await userEvent.click(await screen.findByRole('button', { name: /Field Shirt/ }));
    await userEvent.clear(screen.getByLabelText('Quantity of Field Shirt'));
    await userEvent.type(screen.getByLabelText('Quantity of Field Shirt'), '2');
    await userEvent.click(screen.getByRole('button', { name: 'Add to load' }));
    expect(screen.getByRole('dialog', { name: /Choose variant for Field Shirt/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Pick L / Gold' }));
    expect(screen.getByText('Field Shirt · L / Gold')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Issue load' }));
    await waitFor(() => expect(fieldLoadsAPI.create).toHaveBeenCalledWith({
      agent_id: 1,
      lines: [{ product_id: 22, quantity: 2, variant_id: 55 }],
    }));
  });

  test('corrected: selling a variant load line posts that variant_id', async () => {
    const variantLoad = {
      id: 11,
      status: 'open',
      agent_name: 'Asha',
      reference: 'FL-2026-11',
      units_sold: 0,
      lines: [{
        id: 3,
        product_id: 22,
        variant_id: 55,
        product_name: 'Field Shirt · L / Gold',
        quantity_taken: 8,
        quantity_sold: 0,
        quantity_returned: null,
        quantity_missing: null,
        still_out: 8,
        available: 8,
        unit_price: '50.00',
      }],
      money: { expected: '0.00', collected: '0.00', cash: '0.00', mpesa: '0.00', credit: '0.00' },
      sales: [],
    };
    fieldLoadsAPI.list.mockResolvedValue({
      data: { can_issue: false, can_approve: true, results: [variantLoad] },
    });
    fieldLoadsAPI.sell.mockResolvedValue({ data: variantLoad });
    render(<FieldLoadsPage />);
    await userEvent.click(await screen.findByRole('button', { name: /Asha/ }));
    expect(screen.getByText('Field Shirt · L / Gold')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Quantity of Field Shirt · L / Gold'), '2');
    await userEvent.click(screen.getByRole('button', { name: 'Record a field load sale' }));
    await waitFor(() => expect(fieldLoadsAPI.sell).toHaveBeenCalledWith(11, expect.objectContaining({
      lines: [{ product_id: 22, variant_id: 55, quantity: 2 }],
    })));
  });

  test('module: field load feature off still hides the screen when variants are on', () => {
    localStorage.setItem('enabled_modules', JSON.stringify({
      sales: { is_enabled: true, features: { field_load: { is_enabled: false } } },
      products: { is_enabled: true, features: { product_variants: { is_enabled: true } } },
    }));
    render(<FieldLoadsPage />);
    expect(screen.getByText(/Field loads are turned off/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Find product')).not.toBeInTheDocument();
  });
});
