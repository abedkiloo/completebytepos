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

describe('StockCheckpointsPage save-when-changed', () => {
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
      data: { id: 11, status: 'counted', counted_qty: 8 },
    });
    inventoryAPI.countCheckpointAll.mockResolvedValue({
      data: { counted: 1, lines: [] },
    });
  });

  async function openDetail() {
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /March count/i }));
    await screen.findByText('Widget');
  }

  it('keeps Save count and Save all disabled when drafts match system qty', async () => {
    await openDetail();
    const saveButtons = screen.getAllByRole('button', { name: /^Save count$/i });
    expect(saveButtons).toHaveLength(2);
    saveButtons.forEach((btn) => expect(btn).toBeDisabled());
    expect(screen.getByRole('button', { name: /Save all counts/i })).toBeDisabled();
  });

  it('enables Save count only for the row whose qty changed', async () => {
    await openDetail();
    const inputs = screen.getAllByRole('spinbutton');
    expect(inputs).toHaveLength(2);
    fireEvent.change(inputs[0], { target: { value: '8' } });
    const saveButtons = screen.getAllByRole('button', { name: /^Save count$/i });
    expect(saveButtons[0]).not.toBeDisabled();
    expect(saveButtons[1]).toBeDisabled();
    expect(screen.getByRole('button', { name: /Save all counts/i })).not.toBeDisabled();
  });

  it('does not call the API when Save stays disabled (unchanged qty)', async () => {
    await openDetail();
    const saveButtons = screen.getAllByRole('button', { name: /^Save count$/i });
    expect(saveButtons[0]).toBeDisabled();
    fireEvent.click(saveButtons[0]);
    expect(inventoryAPI.countCheckpointLine).not.toHaveBeenCalled();
  });

  it('saves a single changed line', async () => {
    await openDetail();
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '8' } });
    fireEvent.click(screen.getAllByRole('button', { name: /^Save count$/i })[0]);
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointLine).toHaveBeenCalledWith(1, 11, {
        counted_qty: 8,
      });
    });
  });

  it('Save all posts only changed lines', async () => {
    await openDetail();
    fireEvent.change(screen.getAllByRole('spinbutton')[1], { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: /Save all counts/i }));
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointAll).toHaveBeenCalledWith(1, {
        lines: [{ line_id: 12, counted_qty: 1 }],
      });
    });
  });

  it('shows restricted empty state without inventory manage', async () => {
    hasPermission.mockReturnValue(false);
    render(<StockCheckpointsPage />);
    expect(await screen.findByText(/Checkpoints are restricted/i)).toBeInTheDocument();
    expect(inventoryAPI.checkpoints).not.toHaveBeenCalled();
  });
});
