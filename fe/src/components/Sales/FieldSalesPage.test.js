import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import FieldSalesPage from './FieldSalesPage';
import { dispatchAPI, deliveryAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission, userMayViewDeliveryHistory } from '../../utils/roleAccess';

jest.mock('../../services/api', () => ({
  dispatchAPI: {
    list: jest.fn(),
    get: jest.fn(),
    drivers: jest.fn(),
    createDriver: jest.fn(),
    pack: jest.fn(),
    assign: jest.fn(),
  },
  deliveryAPI: {
    todayGeometry: jest.fn(),
    staffGeometry: jest.fn(),
    staffRoute: jest.fn(),
    listRoutes: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
  hasPermission: jest.fn(),
  userMayViewDeliveryHistory: jest.fn(),
}));

const submittedOrder = {
  id: 44,
  status: 'submitted',
  customer_name: 'Ada',
  created_at: '2026-09-18T10:00:00Z',
  notes: 'Call first',
  site_detail: {
    label: 'Gate',
    latitude: -1.2,
    longitude: 36.8,
    landmark: 'Blue gate',
  },
  lines: [
    {
      id: 1,
      product_id: 12,
      product_name: 'Cement',
      quantity: 2,
      unit_price: 150,
      line_total: 300,
    },
    {
      product_id: 13,
      variant_id: 2,
      product_name: 'Sand',
      quantity: 1,
      unit_price: 80,
    },
  ],
};

const emptyCartOrder = {
  id: 45,
  status: 'submitted',
  customer_name: 'Ada',
  created_at: '2026-09-18T11:00:00Z',
  site_detail: { latitude: -1.3, longitude: 36.9 },
  lines: [],
};

const readyOrder = {
  id: 46,
  status: 'ready',
  customer_name: 'Ben',
  created_at: '2026-09-18T12:00:00Z',
  stock_allocated: true,
  assigned_delivery_agent_name: null,
  site_detail: {},
  lines: [
    { product_id: 9, product_name: 'Nails', quantity: 3, unit_price: 10, line_total: 30 },
  ],
};

function mockAuth(canPack = true, canViewHistory = false) {
  getStoredAuth.mockReturnValue({ permissions: [{ module: 'dispatch', action: 'update' }] });
  hasPermission.mockReturnValue(canPack);
  userMayViewDeliveryHistory.mockReturnValue(canViewHistory);
}

function mockList(orders, count = orders.length) {
  dispatchAPI.list.mockResolvedValue({ data: { results: orders, count } });
}

describe('FieldSalesPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAuth(true);
    dispatchAPI.drivers.mockResolvedValue({
      data: [{ id: 3, display_name: 'Jane Driver' }],
    });
    dispatchAPI.pack.mockResolvedValue({ data: { ...submittedOrder, status: 'ready' } });
    dispatchAPI.assign.mockResolvedValue({ data: { ...readyOrder, assigned_delivery_agent_id: 3 } });
    dispatchAPI.get.mockResolvedValue({ data: { ...submittedOrder, status: 'ready' } });
    deliveryAPI.staffGeometry.mockResolvedValue({
      data: {
        source: 'straight',
        depot: { latitude: -1.29, longitude: 36.82, label: 'HQ', placeholder: true },
        path: [
          { latitude: -1.29, longitude: 36.82 },
          { latitude: -1.30, longitude: 36.80 },
        ],
        stops: [
          { id: 4, sequence: 1, label: 'Blue gate', latitude: -1.30, longitude: 36.80 },
        ],
      },
    });
    deliveryAPI.staffRoute.mockResolvedValue({
      data: {
        id: 8,
        route_date: '2026-09-24',
        stops: [
          {
            id: 4,
            sequence: 1,
            status: 'completed',
            customer_name: 'Ada',
            collection_amount: '150.00',
          },
        ],
      },
    });
  });

  test('shows confirmation summary before packing and does not POST on cancel', async () => {
    mockList([submittedOrder]);
    render(<FieldSalesPage />);

    expect(await screen.findByTestId('field-sales-pack-44')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('field-sales-pack-44'));
    expect(await screen.findByText('Pack this order?')).toBeInTheDocument();
    expect(screen.getAllByText('Ada').length).toBeGreaterThan(0);
    expect(screen.getByText(/Customer debt/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('commit-confirm-cancel'));
    await waitFor(() => {
      expect(screen.queryByText('Pack this order?')).not.toBeInTheDocument();
    });
    expect(dispatchAPI.pack).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('field-sales-pack-44'));
    fireEvent.click(await screen.findByTestId('commit-confirm-ok'));
    await waitFor(() => expect(dispatchAPI.pack).toHaveBeenCalledWith(44));
    expect(toast.success).toHaveBeenCalled();
  });

  test('validates empty carts and missing driver before opening confirm', async () => {
    mockList([emptyCartOrder, readyOrder]);
    render(<FieldSalesPage />);

    fireEvent.click(await screen.findByTestId('field-sales-pack-45'));
    expect(toast.error).toHaveBeenCalledWith('This order has no products to pack.');
    expect(dispatchAPI.pack).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /^#46$/ }));
    expect(await screen.findByTestId('field-sales-assign')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('field-sales-assign'));
    expect(toast.error).toHaveBeenCalledWith('Select who will deliver first.');
    expect(dispatchAPI.assign).not.toHaveBeenCalled();
  });

  test('assigns from the detail pane after confirmation', async () => {
    mockList([readyOrder]);
    render(<FieldSalesPage />);

    fireEvent.click(await screen.findByRole('button', { name: /View/i }));
    fireEvent.change(await screen.findByTestId('field-sales-driver-select'), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByTestId('field-sales-assign'));
    expect(await screen.findByText('Assign this order?')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('commit-confirm-ok'));
    await waitFor(() =>
      expect(dispatchAPI.assign).toHaveBeenCalledWith(46, { delivery_agent_id: 3 }),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  test('shows assigning label while the assign request is in flight', async () => {
    let finish;
    dispatchAPI.assign.mockImplementation(
      () => new Promise((resolve) => {
        finish = resolve;
      }),
    );
    mockList([readyOrder]);
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByRole('button', { name: /View/i }));
    fireEvent.change(await screen.findByTestId('field-sales-driver-select'), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByTestId('field-sales-assign'));
    fireEvent.click(await screen.findByTestId('commit-confirm-ok'));
    expect(await screen.findByText('Assigning…')).toBeInTheDocument();
    finish({ data: { ...readyOrder, assigned_delivery_agent_id: 3 } });
    await waitFor(() => expect(dispatchAPI.assign).toHaveBeenCalled());
    fireEvent.click(screen.getAllByRole('button', { name: /^Close$/i })[0]);
  });

  test('surfaces pack and assign API errors', async () => {
    mockList([submittedOrder, readyOrder]);
    dispatchAPI.pack.mockRejectedValue({ response: { data: { status: 'Already packed' } } });
    dispatchAPI.assign.mockRejectedValue({
      response: { data: { delivery_agent_id: ['Invalid driver'] } },
    });
    render(<FieldSalesPage />);

    fireEvent.click(await screen.findByTestId('field-sales-pack-44'));
    fireEvent.click(await screen.findByTestId('commit-confirm-ok'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Already packed'));

    fireEvent.click(screen.getByRole('button', { name: /^#46$/ }));
    fireEvent.change(await screen.findByTestId('field-sales-driver-select'), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByTestId('field-sales-assign'));
    fireEvent.click(await screen.findByTestId('commit-confirm-ok'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Invalid driver'));
  });

  test('load error then empty refresh', async () => {
    dispatchAPI.list.mockRejectedValueOnce({ response: { data: { detail: 'Nope' } } });
    render(<FieldSalesPage />);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Nope'));

    dispatchAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
    fireEvent.click(screen.getAllByRole('button', { name: /Refresh/i })[0]);
    await waitFor(() => expect(screen.getByText('No field sales')).toBeInTheDocument());
  });

  test('array payload, packed label, and view-only mode', async () => {
    dispatchAPI.list.mockResolvedValue({ data: [readyOrder] });
    dispatchAPI.drivers.mockRejectedValue(new Error('drivers down'));
    render(<FieldSalesPage />);
    expect(await screen.findByText('#46')).toBeInTheDocument();
    expect(screen.getByText('Packed')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('field-sales-status'), { target: { value: 'done' } });
    fireEvent.change(screen.getByPlaceholderText('Name, phone, or order #'), {
      target: { value: ' ada ' },
    });
    fireEvent.change(screen.getByTestId('field-sales-date-from'), {
      target: { value: '2026-09-01' },
    });
    fireEvent.change(screen.getByTestId('field-sales-date-to'), {
      target: { value: '2026-09-18' },
    });
    await waitFor(() => expect(dispatchAPI.list).toHaveBeenCalled());
  });

  test('hides pack actions without dispatch permission', async () => {
    mockAuth(false);
    mockList([submittedOrder]);
    render(<FieldSalesPage />);
    expect(await screen.findByText('#44')).toBeInTheDocument();
    expect(screen.queryByTestId('field-sales-pack-44')).not.toBeInTheDocument();
  });

  test('generic API fallbacks and assigned-driver detail', async () => {
    const assigned = {
      ...readyOrder,
      id: 47,
      assigned_delivery_agent_id: 3,
      assigned_delivery_agent_name: 'Jane Driver',
      status: 'mystery_status',
    };
    dispatchAPI.list.mockRejectedValueOnce({});
    render(<FieldSalesPage />);
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('Failed to load field sales'),
    );

    dispatchAPI.list.mockResolvedValue({ data: { results: [assigned], count: 1 } });
    dispatchAPI.pack.mockRejectedValue({ message: 'offline' });
    fireEvent.click(screen.getAllByRole('button', { name: /Refresh/i })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /View/i }));
    expect(screen.getByText('Jane Driver')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /^Close$/i })[0]);
  });

  test('paginates when there are more orders than one page', async () => {
    mockList([submittedOrder], 25);
    render(<FieldSalesPage />);
    fireEvent.click((await screen.findAllByRole('button', { name: /Next/i }))[0]);
    await waitFor(() =>
      expect(dispatchAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2 }),
      ),
    );
  });

  test('detail pack refreshes the selected order and shows location extras', async () => {
    mockList([submittedOrder]);
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByRole('button', { name: /View/i }));
    expect(screen.getByText('Blue gate')).toBeInTheDocument();
    expect(screen.getByText('Call first')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('field-sales-pack-detail'));
    fireEvent.click(await screen.findByTestId('commit-confirm-ok'));
    await waitFor(() => expect(dispatchAPI.pack).toHaveBeenCalledWith(44));
    await waitFor(() => expect(dispatchAPI.get).toHaveBeenCalledWith(44));
  });

  test('opens add-driver dialog from the field sales header', async () => {
    mockList([readyOrder]);
    dispatchAPI.createDriver.mockResolvedValue({
      data: { id: 9, display_name: 'New Driver', temporary_password: 'tmp9' },
    });
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-add-driver'));
    expect(screen.getByTestId('add-driver-dialog')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: /View/i }));
    fireEvent.click(screen.getByTestId('field-sales-add-driver-detail'));
    expect(screen.getAllByTestId('add-driver-dialog').length).toBeGreaterThan(0);
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'New Driver' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    expect(await screen.findByTestId('add-driver-temp-password')).toHaveTextContent('tmp9');
    fireEvent.click(screen.getByTestId('add-driver-done'));
  });

  test('ignores invalid or duplicate drivers from add-driver', async () => {
    mockList([readyOrder]);
    dispatchAPI.createDriver
      .mockResolvedValueOnce({ data: { display_name: 'No Id' } })
      .mockResolvedValueOnce({ data: { id: 3, display_name: 'Jane Driver' } });
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-add-driver'));
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'No Id' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    expect(await screen.findByTestId('add-driver-done')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('add-driver-done'));
    fireEvent.click(screen.getByTestId('field-sales-add-driver'));
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'Jane Driver' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    expect(await screen.findByTestId('add-driver-done')).toBeInTheDocument();
  });

  test('loads a planned driver map for staff', async () => {
    mockList([readyOrder]);
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-driver-map'));
    expect(await screen.findByTestId('field-sales-map-panel')).toBeInTheDocument();
    await waitFor(() => expect(deliveryAPI.staffGeometry).toHaveBeenCalled());
    expect(await screen.findByTestId('delivery-route-map-fallback')).toBeInTheDocument();
    expect(screen.getByTestId('field-sales-map-today-only')).toBeInTheDocument();
    expect(screen.queryByTestId('field-sales-map-date')).not.toBeInTheDocument();
    expect(await screen.findByTestId('field-sales-map-stops')).toHaveTextContent('Ada');
    fireEvent.change(screen.getByTestId('field-sales-map-driver'), { target: { value: '3' } });
    await waitFor(() =>
      expect(deliveryAPI.staffGeometry).toHaveBeenCalledWith(
        expect.objectContaining({ agent_id: '3' }),
      ),
    );
  });

  test('managers can pick a previous route date', async () => {
    mockAuth(true, true);
    mockList([readyOrder]);
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-driver-map'));
    const dateInput = await screen.findByTestId('field-sales-map-date');
    fireEvent.change(dateInput, { target: { value: '2026-09-20' } });
    await waitFor(() =>
      expect(deliveryAPI.staffRoute).toHaveBeenCalledWith(
        expect.objectContaining({ agent_id: '3', date: '2026-09-20' }),
      ),
    );
  });

  test('driver map fetch error still shows the panel', async () => {
    mockList([readyOrder]);
    deliveryAPI.staffGeometry.mockRejectedValue(new Error('offline'));
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-driver-map'));
    expect(await screen.findByTestId('field-sales-map-panel')).toBeInTheDocument();
    await waitFor(() => expect(deliveryAPI.staffGeometry).toHaveBeenCalled());
    expect(await screen.findByTestId('delivery-route-map-empty')).toBeInTheDocument();
    expect(screen.getByTestId('field-sales-map-stops-empty')).toBeInTheDocument();
  });

  test('driver map 403 explains the permission block', async () => {
    mockList([readyOrder]);
    const err = new Error('forbidden');
    err.response = { status: 403, data: { detail: 'You cannot view this driver’s route.' } };
    deliveryAPI.staffGeometry.mockRejectedValue(err);
    render(<FieldSalesPage />);
    fireEvent.click(await screen.findByTestId('field-sales-driver-map'));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('You cannot view this driver’s route.'),
    );
  });
});
