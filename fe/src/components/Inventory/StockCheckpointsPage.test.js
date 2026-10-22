import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StockCheckpointsPage from './StockCheckpointsPage';
import { inventoryAPI } from '../../services/api';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';

jest.mock('../../services/api', () => ({
  inventoryAPI: {
    checkpoints: jest.fn(),
    checkpoint: jest.fn(),
    openCheckpoint: jest.fn(),
    countCheckpointLine: jest.fn(),
    countCheckpointAll: jest.fn(),
    closeCheckpoint: jest.fn(),
    cancelCheckpoint: jest.fn(),
  },
  productsAPI: { list: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
  hasPermission: jest.fn(),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({
    settings: { block_sales_during_checkpoint: true },
    loading: false,
  }),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

const openCheckpoint = {
  id: 1,
  title: 'March count',
  status: 'open',
  block_sales: true,
  pending_line_count: 2,
  counted_line_count: 0,
  line_count: 2,
  opened_at: '2026-10-19T08:00:00Z',
  lines: [
    {
      id: 11,
      product_name: 'Widget',
      product_sku: 'W1',
      variant_label: null,
      system_qty_at_open: 10,
      counted_qty: null,
      status: 'pending',
    },
    {
      id: 12,
      product_name: 'Gadget',
      product_sku: 'G1',
      variant_label: null,
      system_qty_at_open: 4,
      counted_qty: null,
      status: 'pending',
    },
  ],
};

const fullyCountedCheckpoint = {
  ...openCheckpoint,
  pending_line_count: 0,
  counted_line_count: 2,
  lines: [
    {
      id: 11,
      product_name: 'Widget',
      product_sku: 'W1',
      variant_label: null,
      system_qty_at_open: 10,
      counted_qty: 10,
      status: 'counted',
    },
    {
      id: 12,
      product_name: 'Gadget',
      product_sku: 'G1',
      variant_label: null,
      system_qty_at_open: 4,
      counted_qty: 1,
      status: 'counted',
    },
  ],
};

describe('StockCheckpointsPage confirm unchanged + close summary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getStoredAuth.mockReturnValue({
      permissions: [{ module: 'inventory', action: 'manage' }],
    });
    hasPermission.mockReturnValue(true);
    inventoryAPI.checkpoints.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            title: 'March count',
            status: 'open',
            block_sales: true,
            pending_line_count: 2,
            counted_line_count: 0,
            line_count: 2,
            opened_at: '2026-10-19T08:00:00Z',
          },
        ],
      },
    });
    inventoryAPI.checkpoint.mockResolvedValue({ data: openCheckpoint });
    inventoryAPI.countCheckpointLine.mockResolvedValue({
      data: { id: 11, status: 'counted', counted_qty: 10 },
    });
    inventoryAPI.countCheckpointAll.mockResolvedValue({
      data: { counted: 2, lines: [] },
    });
    inventoryAPI.closeCheckpoint.mockResolvedValue({
      data: { id: 1, status: 'closed' },
    });
  });

  async function openDetail(checkpoint = openCheckpoint) {
    inventoryAPI.checkpoint.mockResolvedValue({ data: checkpoint });
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /March count/i }));
    await screen.findByText('Widget');
  }

  it('enables Confirm when draft matches system qty', async () => {
    await openDetail();
    const confirmButtons = screen.getAllByRole('button', { name: /^Confirm$/i });
    expect(confirmButtons.length).toBeGreaterThanOrEqual(2);
    confirmButtons.forEach((btn) => expect(btn).not.toBeDisabled());
    expect(screen.getByRole('button', { name: /Confirm all/i })).not.toBeDisabled();
  });

  it('labels a changed pending row as Save count', async () => {
    await openDetail();
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '8' } });
    expect(screen.getByRole('button', { name: /^Save count$/i })).not.toBeDisabled();
  });

  it('confirms an unchanged line without forcing a fake delta', async () => {
    await openDetail();
    fireEvent.click(screen.getAllByRole('button', { name: /^Confirm$/i })[0]);
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointLine).toHaveBeenCalledWith(1, 11, {
        counted_qty: 10,
      });
    });
  });

  it('Confirm all posts every pending line including unchanged', async () => {
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointAll).toHaveBeenCalledWith(1, {
        lines: [
          { line_id: 11, counted_qty: 10 },
          { line_id: 12, counted_qty: 4 },
        ],
      });
    });
  });

  it('shows close summary before closing', async () => {
    inventoryAPI.checkpoints.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            title: 'March count',
            status: 'open',
            pending_line_count: 0,
            counted_line_count: 2,
            line_count: 2,
            opened_at: '2026-10-19T08:00:00Z',
          },
        ],
      },
    });
    await openDetail(fullyCountedCheckpoint);
    fireEvent.click(screen.getByRole('button', { name: /Close checkpoint/i }));
    expect(await screen.findByText(/Close this checkpoint/i)).toBeInTheDocument();
    expect(screen.getByText(/Unchanged/i)).toBeInTheDocument();
    expect(screen.getByText(/Largest adjustments/i)).toBeInTheDocument();
    expect(inventoryAPI.closeCheckpoint).not.toHaveBeenCalled();

    const confirmClose = screen.getAllByRole('button', { name: /Close checkpoint/i }).pop();
    fireEvent.click(confirmClose);
    await waitFor(() => {
      expect(inventoryAPI.closeCheckpoint).toHaveBeenCalledWith(1);
    });
  });

  it('shows restricted empty state without inventory manage', async () => {
    hasPermission.mockReturnValue(false);
    render(<StockCheckpointsPage />);
    expect(await screen.findByText(/Checkpoints are restricted/i)).toBeInTheDocument();
    expect(inventoryAPI.checkpoints).not.toHaveBeenCalled();
  });
});
