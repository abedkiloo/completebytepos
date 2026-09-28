import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReceiptDialog from './ReceiptDialog';
import { printThermalReceipt } from './printReceipt';
import { toast } from '../../../utils/toast';

jest.mock('../../Customers/CustomerFormModal', () => () => null);

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: {} }),
}));

jest.mock('./useStoreInfo', () => ({
  useStoreInfo: () => ({ storeName: 'Test Store', phone: '0718515142' }),
}));

jest.mock('./ThermalReceipt', () => {
  const { forwardRef } = require('react');
  return {
    ThermalReceipt: forwardRef((props, ref) => (
      <div data-testid="thermal-receipt" ref={ref} />
    )),
  };
});

jest.mock('./printReceipt', () => ({
  printThermalReceipt: jest.fn().mockResolvedValue(true),
}));

jest.mock('html-to-image', () => ({
  toPng: jest.fn(),
}));

jest.mock('../../../utils/toast', () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
    warning: jest.fn(),
  },
}));

jest.mock('../../../utils/roleAccess', () => ({
  isManagerOrAdminFromStorage: () => false,
  getStoredAuth: () => ({ permissions: [] }),
}));

const PNG_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

const sale = {
  id: 1,
  sale_number: 'S-001',
  total: '100.00',
  amount_paid: '100.00',
  customer_name: 'Walk-in',
};

describe('ReceiptDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows Done and closes the dialog', () => {
    const onOpenChange = jest.fn();

    render(
      <ReceiptDialog sale={sale} open onOpenChange={onOpenChange} autoPrint={false} />
    );

    fireEvent.click(screen.getByRole('button', { name: /Done/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('does not show email action and prioritises print', () => {
    render(
      <ReceiptDialog sale={sale} open onOpenChange={jest.fn()} autoPrint={false} />
    );

    expect(screen.queryByRole('button', { name: /Email/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('receipt-print-button')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Print receipt/i })).toBeInTheDocument();
  });

  it('prints through the existing pdf path', async () => {
    render(
      <ReceiptDialog sale={sale} open onOpenChange={jest.fn()} autoPrint={false} />
    );

    fireEvent.click(screen.getByTestId('receipt-print-button'));
    await waitFor(() => expect(printThermalReceipt).toHaveBeenCalledTimes(1));
    expect(printThermalReceipt).toHaveBeenCalledWith(
      expect.objectContaining({ sale })
    );
  });

  it('toasts when print dialog cannot open', async () => {
    printThermalReceipt.mockResolvedValueOnce(false);
    render(
      <ReceiptDialog sale={sale} open onOpenChange={jest.fn()} autoPrint={false} />
    );

    fireEvent.click(screen.getByTestId('receipt-print-button'));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        'Could not open the print dialog. Check pop-up settings.'
      )
    );
  });

  it('renders nothing without a sale', () => {
    const { container } = render(
      <ReceiptDialog sale={null} open onOpenChange={jest.fn()} autoPrint={false} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('shares a png snapshot of the on-screen receipt', async () => {
    const capturePng = jest.fn().mockResolvedValue(PNG_DATA_URL);
    const shareReceiptPng = jest.fn().mockResolvedValue({ method: 'share' });

    render(
      <ReceiptDialog
        sale={sale}
        open
        onOpenChange={jest.fn()}
        autoPrint={false}
        capturePng={capturePng}
        shareReceiptPng={shareReceiptPng}
      />
    );

    fireEvent.click(screen.getByTestId('receipt-share-button'));
    await waitFor(() => expect(capturePng).toHaveBeenCalled());
    expect(shareReceiptPng).toHaveBeenCalledWith(
      expect.objectContaining({
        pngDataUrl: PNG_DATA_URL,
        sale,
      })
    );
    expect(printThermalReceipt).not.toHaveBeenCalled();
  });

  it('downloads the png and opens WhatsApp text when file share is unavailable', async () => {
    const openWindow = jest.fn();
    const shareReceiptPng = jest.fn().mockResolvedValue({
      method: 'download',
      caption: 'Receipt S-001',
    });

    render(
      <ReceiptDialog
        sale={{ ...sale, customer_phone: '0712345678' }}
        open
        onOpenChange={jest.fn()}
        autoPrint={false}
        capturePng={jest.fn().mockResolvedValue(PNG_DATA_URL)}
        shareReceiptPng={shareReceiptPng}
        openWindow={openWindow}
      />
    );

    fireEvent.click(screen.getByTestId('receipt-share-button'));
    await waitFor(() =>
      expect(openWindow).toHaveBeenCalledWith(
        expect.stringContaining('https://wa.me/0712345678'),
        '_blank',
        'noopener,noreferrer'
      )
    );
  });

  it('saves the png and explains how to share when there is no customer phone', async () => {
    render(
      <ReceiptDialog
        sale={sale}
        open
        onOpenChange={jest.fn()}
        autoPrint={false}
        capturePng={jest.fn().mockResolvedValue(PNG_DATA_URL)}
        shareReceiptPng={jest.fn().mockResolvedValue({ method: 'download' })}
      />
    );

    fireEvent.click(screen.getByTestId('receipt-share-button'));
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith(
        'Receipt photo saved. Share it from your downloads.'
      )
    );
  });

  it('does not toast when the user cancels the share sheet', async () => {
    const abort = Object.assign(new Error('cancelled'), { name: 'AbortError' });
    render(
      <ReceiptDialog
        sale={sale}
        open
        onOpenChange={jest.fn()}
        autoPrint={false}
        capturePng={jest.fn().mockRejectedValue(abort)}
      />
    );

    fireEvent.click(screen.getByTestId('receipt-share-button'));
    await waitFor(() => expect(screen.getByTestId('receipt-share-button')).not.toBeDisabled());
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('toasts when the snapshot cannot be created', async () => {
    render(
      <ReceiptDialog
        sale={sale}
        open
        onOpenChange={jest.fn()}
        autoPrint={false}
        capturePng={jest.fn().mockRejectedValue(new Error('boom'))}
      />
    );

    fireEvent.click(screen.getByTestId('receipt-share-button'));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('Could not create receipt photo.')
    );
  });
});
