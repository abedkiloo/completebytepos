import React from 'react';
import { render, screen } from '@testing-library/react';
import { WALK_IN_CUSTOMER } from '../../../utils/walkInCustomer';

jest.mock('../../../services/api', () => ({
  productsAPI: {},
  customersAPI: {},
  salesAPI: {},
}));
jest.mock('./useBillingPOSState', () => ({
  __esModule: true,
  useBillingPOSState: jest.fn(),
}));
jest.mock('../../../hooks/useStoreSettings');
jest.mock('../../../hooks/useModuleSettings');
jest.mock('../../../utils/roleAccess', () => ({
  isManagerOrAdminFromStorage: jest.fn(() => false),
}));
jest.mock('../VariantSelector', () => () => null);
jest.mock('../PosCartRecoveryDialog', () => () => null);
jest.mock('./PartialPaymentCustomerDialog', () => () => null);
jest.mock('../../Customers/CustomerFormModal', () => () => null);
jest.mock('../v2/ReceiptDialog', () => () => null);

import BillingPOSPage from './BillingPOSPage';

const { useBillingPOSState } = require('./useBillingPOSState');
const { useStoreSettings } = require('../../../hooks/useStoreSettings');
const { useModuleSettings } = require('../../../hooks/useModuleSettings');

function buildMockState(overrides = {}) {
  return {
    loadingHolding: false,
    searchQuery: '',
    setSearchQuery: jest.fn(),
    searchResults: [],
    searching: false,
    cart: [
      {
        id: 1,
        name: 'Item A',
        quantity: 1,
        selling_price: 500,
        price: 500,
        mrp: 500,
      },
    ],
    itemCount: 1,
    subtotal: 500,
    discountAmount: 0,
    taxableValue: 500,
    taxAmount: 0,
    total: 500,
    taxPct: '0',
    setTaxPct: jest.fn(),
    discount: '0',
    setDiscount: jest.fn(),
    discountType: 'flat',
    setDiscountType: jest.fn(),
    paymentMethod: 'cash',
    setPaymentMethod: jest.fn(),
    partialPayment: false,
    setPartialPayment: jest.fn(),
    attemptSetPartialPayment: jest.fn(),
    partialPaymentCustomerPrompt: false,
    closePartialPaymentCustomerPrompt: jest.fn(),
    amountPaid: '',
    setAmountPaid: jest.fn(),
    selectedCustomer: WALK_IN_CUSTOMER,
    setSelectedCustomer: jest.fn(),
    selectWalkInCustomer: jest.fn(),
    loadCustomers: jest.fn(),
    isWalkInCustomer: (c) => c?.id === 'walk-in' || c?.id === WALK_IN_CUSTOMER.id,
    customerQuery: '',
    setCustomerQuery: jest.fn(),
    filteredCustomers: [],
    holdingNumber: 'HOLD-1',
    syncingHolding: false,
    submitting: false,
    addToCart: jest.fn(),
    updateQty: jest.fn(),
    setQty: jest.fn(),
    removeLine: jest.fn(),
    clearCart: jest.fn(),
    checkout: jest.fn(),
    variantPickerProduct: null,
    setVariantPickerProduct: jest.fn(),
    lastSale: null,
    showReceipt: false,
    setShowReceipt: jest.fn(),
    showDiscount: false,
    showTax: false,
    allowPartialPayment: true,
    requireCustomer: false,
    validateStock: false,
    cartRecovery: null,
    recoveryBusy: false,
    continueCartRecovery: jest.fn(),
    startNewSaleFromRecovery: jest.fn(),
    ...overrides,
  };
}

describe('BillingPOSPage invoice layout', () => {
  beforeEach(() => {
    useStoreSettings.mockReturnValue({
      settings: { enabled_payment_methods: ['cash', 'wallet'] },
    });
    useModuleSettings.mockReturnValue({ settings: {} });
    useBillingPOSState.mockReturnValue(buildMockState());
  });

  it('renders payment mode before amount received with visible labels', () => {
    render(<BillingPOSPage />);

    const paymentSection = screen.getByTestId('billing-payment-section');
    const amountBlock = screen.getByTestId('billing-amount-received');

    expect(paymentSection).toBeInTheDocument();
    expect(amountBlock).toBeInTheDocument();
    expect(paymentSection).toContainElement(amountBlock);

    expect(screen.getByLabelText(/Amount received/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Partial payment \(balance on customer account\)/i)
    ).toBeInTheDocument();
  });

  it('keeps amount received inside payment section when partial payment is off', () => {
    useBillingPOSState.mockReturnValue(
      buildMockState({ allowPartialPayment: false })
    );
    render(<BillingPOSPage />);

    expect(screen.queryByText(/Partial payment/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('billing-amount-received')).toBeInTheDocument();
  });
});
