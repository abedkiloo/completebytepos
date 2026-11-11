import {
  collectionPayerDetailsEnabled,
  mpesaDestinationLabel,
  normalizePayerPhone,
  validateCollectionPayerFields,
} from './collectionPayer';

jest.mock('./moduleFeatures', () => ({
  isModuleFeatureEnabled: jest.fn(() => true),
}));

const { isModuleFeatureEnabled } = require('./moduleFeatures');

describe('collectionPayer', () => {
  beforeEach(() => {
    isModuleFeatureEnabled.mockReturnValue(true);
  });

  it('reads the customers collection_payer_details feature', () => {
    expect(collectionPayerDetailsEnabled()).toBe(true);
    expect(isModuleFeatureEnabled).toHaveBeenCalledWith(
      'customers',
      'collection_payer_details',
      true
    );
  });

  it('labels till and bank', () => {
    expect(mpesaDestinationLabel('till')).toBe('Till');
    expect(mpesaDestinationLabel('BANK')).toBe('Bank');
    expect(mpesaDestinationLabel('')).toBe('');
  });

  it('normalizes payer phones', () => {
    expect(normalizePayerPhone('+254 712-345-678')).toBe('+254712345678');
    expect(normalizePayerPhone('0712 345 678')).toBe('0712345678');
  });

  it('does not require who-paid for cash even when the feature is on', () => {
    const errors = validateCollectionPayerFields({
      paymentMethod: 'cash',
      requirePayer: true,
    });
    expect(errors).toEqual({});
  });

  it('requires payer name and phone for non-cash when feature validation is on', () => {
    const errors = validateCollectionPayerFields({
      paymentMethod: 'mpesa',
      reference: 'QHX7K2L9M1',
      mpesaDestination: 'till',
      requirePayer: true,
      requireMpesaDestinationForCode: true,
    });
    expect(errors.payer_name).toMatch(/who paid/i);
    expect(errors.payer_phone).toMatch(/phone/i);
  });

  it('requires till or bank before an M-Pesa code is saved', () => {
    const errors = validateCollectionPayerFields({
      paymentMethod: 'mpesa',
      reference: 'QHX7K2L9M1',
      payerName: 'Ann',
      payerPhone: '0712345678',
      mpesaDestination: '',
      requirePayer: true,
      requireMpesaDestinationForCode: true,
    });
    expect(errors.mpesa_destination).toMatch(/till or bank/i);
  });

  it('accepts a complete mpesa till collection', () => {
    const errors = validateCollectionPayerFields({
      paymentMethod: 'mpesa',
      reference: 'QHX7K2L9M1',
      payerName: 'Ann',
      payerPhone: '0712345678',
      mpesaDestination: 'till',
    });
    expect(errors).toEqual({});
  });

  it('rejects invalid destination and short phones', () => {
    expect(
      validateCollectionPayerFields({
        paymentMethod: 'mpesa',
        reference: 'QHX7K2L9M1',
        payerName: 'Ann',
        payerPhone: '0712345678',
        mpesaDestination: 'paypal',
      }).mpesa_destination
    ).toMatch(/till or bank/i);

    expect(
      validateCollectionPayerFields({
        paymentMethod: 'cash',
        payerName: 'Ann',
        payerPhone: '12345',
      }).payer_phone
    ).toMatch(/at least 9/i);
  });
});
