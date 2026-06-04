import {
  invoiceCreationAllowed,
  paymentTrackingAllowed,
} from './invoicingAccess';

jest.mock('./moduleFeatures', () => ({
  isModuleFeatureEnabled: jest.fn(),
}));

jest.mock('./moduleSettings', () => ({
  isModuleEnabled: jest.fn(),
}));

const { isModuleFeatureEnabled } = require('./moduleFeatures');
const { isModuleEnabled } = require('./moduleSettings');

describe('invoicingAccess', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    isModuleEnabled.mockReturnValue(true);
    isModuleFeatureEnabled.mockReturnValue(true);
  });

  test('invoiceCreationAllowed requires module and feature', () => {
    expect(invoiceCreationAllowed()).toBe(true);
    isModuleEnabled.mockReturnValue(false);
    expect(invoiceCreationAllowed()).toBe(false);
    isModuleEnabled.mockReturnValue(true);
    isModuleFeatureEnabled.mockReturnValue(false);
    expect(invoiceCreationAllowed()).toBe(false);
  });

  test('paymentTrackingAllowed requires module and feature', () => {
    isModuleFeatureEnabled.mockImplementation((_m, key) => key === 'payment_tracking');
    expect(paymentTrackingAllowed()).toBe(true);
    isModuleFeatureEnabled.mockReturnValue(false);
    expect(paymentTrackingAllowed()).toBe(false);
  });
});
