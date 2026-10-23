import React from 'react';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import StockCheckpointsPage from './StockCheckpointsPage';
import { inventoryAPI, productsAPI } from '../../services/api';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { toast } from '../../utils/toast';
import * as checkpointDrafts from '../../utils/checkpointCountDrafts';

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
      variant_label: 'Large',
      system_qty_at_open: 4,
      counted_qty: 1,
      status: 'counted',
    },
  ],
};

const allUnchangedCounted = {
  ...fullyCountedCheckpoint,
  lines: fullyCountedCheckpoint.lines.map((line) => ({
    ...line,
    counted_qty: line.system_qty_at_open,
  })),
};

describe('StockCheckpointsPage confirm unchanged + close summary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
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
    inventoryAPI.cancelCheckpoint.mockResolvedValue({
      data: { id: 1, status: 'cancelled' },
    });
    inventoryAPI.openCheckpoint.mockResolvedValue({
      data: { id: 9, title: 'New CP', status: 'open' },
    });
    productsAPI.list.mockResolvedValue({ data: { results: [{ id: 77, name: 'Cup' }] } });
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
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringMatching(/Confirmed Widget/)
    );
  });

  it('saves a changed count and toasts Counted', async () => {
    await openDetail();
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '8' } });
    fireEvent.click(screen.getByRole('button', { name: /^Save count$/i }));
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointLine).toHaveBeenCalledWith(1, 11, {
        counted_qty: 8,
      });
    });
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/Counted Widget/));
  });

  it('corrects an already counted line', async () => {
    await openDetail(fullyCountedCheckpoint);
    fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '12' } });
    fireEvent.click(screen.getAllByRole('button', { name: /^Correct$/i })[0]);
    await waitFor(() => {
      expect(inventoryAPI.countCheckpointLine).toHaveBeenCalledWith(1, 11, {
        counted_qty: 12,
      });
    });
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringMatching(/Corrected Widget to 12/)
    );
  });

  it('shows form error when count API fails', async () => {
    inventoryAPI.countCheckpointLine.mockRejectedValueOnce({
      response: { data: { error: 'Line locked' } },
    });
    await openDetail();
    fireEvent.click(screen.getAllByRole('button', { name: /^Confirm$/i })[0]);
    expect(await screen.findByText('Line locked')).toBeInTheDocument();
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

  it('Confirm all shows API error', async () => {
    inventoryAPI.countCheckpointAll.mockRejectedValueOnce({
      response: { data: { error: 'Batch failed' } },
    });
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    expect(await screen.findByText('Batch failed')).toBeInTheDocument();
  });

  it('Confirm all when nothing pending shows banner', async () => {
    await openDetail(fullyCountedCheckpoint);
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    expect(await screen.findByText(/All lines are already counted/i)).toBeInTheDocument();
  });

  it('blocks close while lines are still pending with a banner', async () => {
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /Close checkpoint/i }));
    expect(
      await screen.findByText(/Confirm every line first/i)
    ).toBeInTheDocument();
    expect(inventoryAPI.closeCheckpoint).not.toHaveBeenCalled();
  });

  it('shows close summary before closing and can dismiss', async () => {
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
    expect(screen.getByText(/Largest adjustments/i)).toBeInTheDocument();
    expect(inventoryAPI.closeCheckpoint).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Keep open/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Close this checkpoint\?/i)).not.toBeInTheDocument();
    });
  });

  it('shows unchanged summary copy when every line matches system', async () => {
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
    await openDetail(allUnchangedCounted);
    fireEvent.click(screen.getByRole('button', { name: /Close checkpoint/i }));
    expect(
      await screen.findByText(/closing will not change inventory quantities/i)
    ).toBeInTheDocument();
  });

  it('closes after confirming the summary', async () => {
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
    await screen.findByText(/Close this checkpoint/i);
    const confirmClose = screen.getAllByRole('button', { name: /Close checkpoint/i }).pop();
    fireEvent.click(confirmClose);
    await waitFor(() => {
      expect(inventoryAPI.closeCheckpoint).toHaveBeenCalledWith(1);
    });
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringMatching(/Checkpoint closed/)
    );
  });

  it('shows close API error in the banner', async () => {
    inventoryAPI.closeCheckpoint.mockRejectedValueOnce({
      response: { data: { error: 'Still pending on server' } },
    });
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
    await screen.findByText(/Close this checkpoint/i);
    fireEvent.click(screen.getAllByRole('button', { name: /Close checkpoint/i }).pop());
    expect(await screen.findByText('Still pending on server')).toBeInTheDocument();
  });

  it('cancels a checkpoint after browser confirm', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    await waitFor(() => {
      expect(inventoryAPI.cancelCheckpoint).toHaveBeenCalledWith(1);
    });
    confirmSpy.mockRestore();
  });

  it('does not cancel when browser confirm is declined', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    expect(inventoryAPI.cancelCheckpoint).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('shows cancel API error', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    inventoryAPI.cancelCheckpoint.mockRejectedValueOnce({
      response: { data: { error: 'Cannot cancel' } },
    });
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    expect(await screen.findByText('Cannot cancel')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('opens a checkpoint with include-all', async () => {
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.change(screen.getByPlaceholderText(/March stocktake/i), {
      target: { value: ' April take ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Open & block sales/i }));
    await waitFor(() => {
      expect(inventoryAPI.openCheckpoint).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'April take',
          include_all_tracked: true,
          block_sales: true,
        })
      );
    });
  });

  it('requires a title before opening', async () => {
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.click(screen.getByRole('button', { name: /Open & block sales/i }));
    expect(await screen.findByText(/Enter a checkpoint title/i)).toBeInTheDocument();
    expect(inventoryAPI.openCheckpoint).not.toHaveBeenCalled();
  });

  it('shows open API error', async () => {
    inventoryAPI.openCheckpoint.mockRejectedValueOnce({
      response: { data: { error: 'Open failed' } },
    });
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.change(screen.getByPlaceholderText(/March stocktake/i), {
      target: { value: 'Fail open' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Open & block sales/i }));
    expect(await screen.findByText('Open failed')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Dismiss message/i }));
    await waitFor(() => {
      expect(screen.queryByText('Open failed')).not.toBeInTheDocument();
    });
  });

  it('searches products when include-all is off', async () => {
    jest.useFakeTimers();
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.click(screen.getByLabelText(/Include all tracked products/i));
    fireEvent.change(screen.getByPlaceholderText(/Search products/i), {
      target: { value: 'cup' },
    });
    await act(async () => {
      jest.advanceTimersByTime(350);
    });
    await waitFor(() => {
      expect(productsAPI.list).toHaveBeenCalled();
    });
    expect(await screen.findByText('Cup')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Cup'));
    expect(screen.getByText(/1 product selected/i)).toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows empty list state', async () => {
    inventoryAPI.checkpoints.mockResolvedValue({ data: { results: [] } });
    render(<StockCheckpointsPage />);
    expect(await screen.findByText(/No checkpoints yet/i)).toBeInTheDocument();
  });

  it('shows list load error', async () => {
    inventoryAPI.checkpoints.mockRejectedValueOnce({
      response: { data: { error: 'List failed' } },
    });
    render(<StockCheckpointsPage />);
    expect(await screen.findByText('List failed')).toBeInTheDocument();
  });

  it('shows detail load error', async () => {
    inventoryAPI.checkpoint.mockRejectedValueOnce({
      response: { data: { error: 'Detail failed' } },
    });
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /March count/i }));
    expect(await screen.findByText('Detail failed')).toBeInTheDocument();
  });

  it('renders closed checkpoint rows', async () => {
    inventoryAPI.checkpoints.mockResolvedValue({
      data: {
        results: [
          {
            id: 2,
            title: 'Closed take',
            status: 'closed',
            pending_line_count: 0,
            counted_line_count: 1,
            line_count: 1,
            opened_at: '2026-10-01T08:00:00Z',
            closed_at: '2026-10-02T08:00:00Z',
          },
        ],
      },
    });
    inventoryAPI.checkpoint.mockResolvedValue({
      data: {
        id: 2,
        title: 'Closed take',
        status: 'closed',
        pending_line_count: 0,
        counted_line_count: 1,
        line_count: 1,
        inventory_value_after: 1200,
        lines: [
          {
            id: 21,
            product_name: 'Closed item',
            system_qty_at_open: 5,
            counted_qty: 5,
            status: 'counted',
          },
        ],
      },
    });
    render(<StockCheckpointsPage />);
    await screen.findByText('Closed take');
    fireEvent.click(screen.getByRole('button', { name: /Closed take/i }));
    expect(await screen.findByText(/Inventory value after count/i)).toBeInTheDocument();
    expect(screen.getByText('Closed item')).toBeInTheDocument();
  });

  it('shows restricted empty state without inventory manage', async () => {
    hasPermission.mockReturnValue(false);
    render(<StockCheckpointsPage />);
    expect(await screen.findByText(/Checkpoints are restricted/i)).toBeInTheDocument();
    expect(inventoryAPI.checkpoints).not.toHaveBeenCalled();
  });

  it('dismisses the form banner', async () => {
    inventoryAPI.checkpoints.mockRejectedValueOnce({
      response: { data: { error: 'Dismiss me' } },
    });
    render(<StockCheckpointsPage />);
    expect(await screen.findByText('Dismiss me')).toBeInTheDocument();
    const dismiss = screen.getByRole('button', { name: /dismiss|close/i });
    fireEvent.click(dismiss);
    await waitFor(() => {
      expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument();
    });
  });

  it('toggles open-dialog options and cancels', async () => {
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.change(screen.getByPlaceholderText(/March stocktake/i), {
      target: { value: 'Notes take' },
    });
    fireEvent.change(screen.getByDisplayValue(''), {
      target: { value: 'Optional notes' },
    });
    fireEvent.click(screen.getByLabelText(/Stop sales on included products/i));
    expect(screen.getByRole('button', { name: /Open \(sales continue\)/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Open stock checkpoint/i)).not.toBeInTheDocument();
    });
  });

  it('handles product search failure', async () => {
    jest.useFakeTimers();
    productsAPI.list.mockRejectedValueOnce(new Error('search failed'));
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    fireEvent.click(screen.getByLabelText(/Include all tracked products/i));
    fireEvent.change(screen.getByPlaceholderText(/Search products/i), {
      target: { value: 'x' },
    });
    await act(async () => {
      jest.advanceTimersByTime(350);
    });
    await waitFor(() => {
      expect(productsAPI.list).toHaveBeenCalled();
    });
    jest.useRealTimers();
  });

  it('renders cancelled status badge', async () => {
    inventoryAPI.checkpoints.mockResolvedValue({
      data: {
        results: [
          {
            id: 3,
            title: 'Cancelled take',
            status: 'cancelled',
            pending_line_count: 0,
            counted_line_count: 0,
            line_count: 1,
            opened_at: '2026-10-01T08:00:00Z',
          },
        ],
      },
    });
    render(<StockCheckpointsPage />);
    expect(await screen.findByText('Cancelled take')).toBeInTheDocument();
    expect(screen.getByText('cancelled')).toBeInTheDocument();
  });

  it('uses fallback detail error when response has no message', async () => {
    inventoryAPI.checkpoint.mockRejectedValueOnce({});
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /March count/i }));
    expect(await screen.findByText(/Could not load checkpoint/i)).toBeInTheDocument();
  });

  it('shows empty-payload banner when confirm-all builds nothing', async () => {
    const spy = jest
      .spyOn(checkpointDrafts, 'buildPendingCountPayload')
      .mockReturnValue({ payload: [] });
    await openDetail();
    fireEvent.click(screen.getByRole('button', { name: /Confirm all/i }));
    expect(
      await screen.findByText(/Enter a valid stock-at-hand quantity for at least one line/i)
    ).toBeInTheDocument();
    spy.mockRestore();
  });

  it('shows unsavable banner when save helpers reject the draft', async () => {
    const spy = jest.spyOn(checkpointDrafts, 'isCountDraftSavable').mockReturnValue(true);
    await openDetail();
    const btn = screen.getAllByRole('button', { name: /^Confirm$/i })[0];
    spy.mockReturnValue(false);
    fireEvent.click(btn);
    expect(
      await screen.findByText(/Enter a valid stock-at-hand quantity/i)
    ).toBeInTheDocument();
    spy.mockRestore();
  });

  it('closes the open dialog via onOpenChange', async () => {
    render(<StockCheckpointsPage />);
    await screen.findByText('March count');
    fireEvent.click(screen.getByRole('button', { name: /Open checkpoint/i }));
    expect(screen.getByText(/Open stock checkpoint/i)).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByText(/Open stock checkpoint/i)).not.toBeInTheDocument();
    });
  });
});
