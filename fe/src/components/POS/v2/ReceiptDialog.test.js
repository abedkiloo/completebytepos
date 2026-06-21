import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ReceiptDialog from './ReceiptDialog';

jest.mock('../../Customers/CustomerFormModal', () => () => null);

jest.mock('../../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: {} }),
}));

jest.mock('./useStoreInfo', () => ({
  useStoreInfo: () => ({ name: 'Test Store' }),
}));

jest.mock('./ThermalReceipt', () => ({
  ThermalReceipt: () => <div data-testid="thermal-receipt" />,
}));

jest.mock('./printReceipt', () => ({
  printThermalReceipt: jest.fn().mockResolvedValue(true),
}));

jest.mock('../../../utils/roleAccess', () => ({
  isManagerOrAdminFromStorage: () => false,
  getStoredAuth: () => ({ permissions: [] }),
}));

const sale = {
  id: 1,
  sale_number: 'S-001',
  total: '100.00',
  amount_paid: '100.00',
  customer_name: 'Walk-in',
};

describe('ReceiptDialog', () => {
  it('shows Cancel and closes the dialog', () => {
    const onOpenChange = jest.fn();

    render(
      <ReceiptDialog sale={sale} open onOpenChange={onOpenChange} autoPrint={false} />
    );

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
