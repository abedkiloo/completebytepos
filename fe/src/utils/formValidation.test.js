import {
  required,
  minLength,
  normalizeApiErrors,
  hasValidationErrors,
  firstErrorField,
  fieldError,
  formGroupClass,
  paymentAmountMessage,
  parsePaymentAmount,
  mpesaReceiptMessage,
  normalizeMpesaReceipt,
  emailMessage,
  phoneMessage,
  personNameMessage,
  dateMessage,
  integerMessage,
  moneyMessage,
  requiredChoiceMessage,
} from './formValidation';

describe('formValidation', () => {
  it('required rejects blank strings', () => {
    expect(required('')).toBe('This field is required');
    expect(required('  ')).toBe('This field is required');
    expect(required('ok')).toBeUndefined();
  });

  it('normalizeApiErrors maps DRF field arrays', () => {
    expect(normalizeApiErrors({ password: ['This field may not be blank.'] })).toEqual({
      password: 'This field may not be blank.',
    });
  });

  it('normalizeApiErrors handles error and detail strings', () => {
    expect(normalizeApiErrors({ error: 'Denied' })).toEqual({ _form: 'Denied' });
    expect(normalizeApiErrors({ detail: 'Not found' })).toEqual({ _form: 'Not found' });
    expect(normalizeApiErrors(null)).toEqual({});
  });

  it('normalizeApiErrors maps string field errors', () => {
    expect(normalizeApiErrors({ name: 'Taken' })).toEqual({ name: 'Taken' });
  });

  it('normalizeApiErrors skips non-string error keys while mapping fields', () => {
    expect(normalizeApiErrors({ error: ['Denied'], email: ['invalid'] })).toEqual({
      email: 'invalid',
    });
  });

  it('normalizeApiErrors maps nested object string values', () => {
    expect(
      normalizeApiErrors({ profile: { phone_number: 'Required' } })
    ).toMatchObject({
      'profile.phone_number': 'Required',
      phone_number: 'Required',
    });
  });

  it('normalizeApiErrors flattens nested objects', () => {
    expect(
      normalizeApiErrors({ profile: { phone_number: ['Required'] } })
    ).toMatchObject({
      'profile.phone_number': 'Required',
      phone_number: 'Required',
    });
  });

  it('required allows non-string values', () => {
    expect(required(null)).toBe('This field is required');
    expect(required(0)).toBeUndefined();
    expect(required(false)).toBeUndefined();
  });

  it('firstErrorField returns null when only _form', () => {
    expect(firstErrorField({ _form: 'bad' })).toBeNull();
  });

  it('firstErrorField skips _form', () => {
    expect(firstErrorField({ _form: 'bad', email: 'invalid' })).toBe('email');
  });

  it('hasValidationErrors', () => {
    expect(hasValidationErrors({})).toBe(false);
    expect(hasValidationErrors({ username: 'x' })).toBe(true);
  });

  it('minLength enforces minimum', () => {
    expect(minLength('', 6)).toBeUndefined();
    expect(minLength('abc', 6)).toContain('6');
    expect(minLength('abc', 6, 'Too short')).toBe('Too short');
    expect(minLength('abcdef', 6)).toBeUndefined();
  });

  it('fieldError reads nested profile keys', () => {
    expect(fieldError({ 'profile.phone_number': 'bad' }, 'phone_number')).toBe('bad');
  });

  it('formGroupClass marks invalid fields', () => {
    expect(formGroupClass({ email: 'invalid' }, 'email', 'extra')).toContain('has-error');
    expect(formGroupClass({ email: 'invalid' }, 'email', 'extra')).toContain('extra');
    expect(formGroupClass({}, 'email')).not.toContain('has-error');
  });

  it('paymentAmountMessage explains empty, invalid, and zero amounts', () => {
    expect(paymentAmountMessage()).toContain('e.g. 250.00');
    expect(paymentAmountMessage(null)).toContain('e.g. 250.00');
    expect(paymentAmountMessage('')).toContain('e.g. 250.00');
    expect(paymentAmountMessage('abc')).toContain('numbers only');
    expect(paymentAmountMessage('12.345')).toContain('2 decimal');
    expect(paymentAmountMessage('0')).toContain('greater than zero');
    expect(paymentAmountMessage('0.00')).toContain('greater than zero');
    expect(paymentAmountMessage('1,250.50')).toBeUndefined();
    expect(parsePaymentAmount('abc')).toBeUndefined();
    expect(parsePaymentAmount('1,250.50')).toBe(1250.5);
    expect(parsePaymentAmount('250')).toBe(250);
  });

  it('mpesaReceiptMessage explains missing, symbols, and short codes', () => {
    expect(mpesaReceiptMessage('')).toContain('at least 4 letters and numbers');
    expect(mpesaReceiptMessage('QHX-7K2')).toContain('letters and numbers only');
    expect(mpesaReceiptMessage('AB1')).toContain('you entered 3');
    expect(mpesaReceiptMessage('AB12')).toBeUndefined();
    expect(mpesaReceiptMessage('ABC12')).toBeUndefined();
    expect(mpesaReceiptMessage('QHX7K2L9M1X')).toBeUndefined();
    expect(mpesaReceiptMessage(' qhx 7k2 l9m1 ')).toBeUndefined();
    expect(mpesaReceiptMessage('QHX7K2L9M1')).toBeUndefined();
    expect(normalizeMpesaReceipt(' qhx 7k2 l9m1 ')).toBe('QHX7K2L9M1');
    expect(normalizeMpesaReceipt(undefined)).toBe('');
  });

  it('fieldError returns undefined without an errors object', () => {
    expect(fieldError(null, 'email')).toBeUndefined();
    expect(fieldError({ email: 'invalid' }, 'email')).toBe('invalid');
  });

  it('emailMessage explains missing and malformed addresses', () => {
    expect(emailMessage('')).toBeUndefined();
    expect(emailMessage('', { required: true })).toContain('e.g. name@example.com');
    expect(emailMessage('not-an-email')).toContain('name@example.com');
    expect(emailMessage('not-an-email')).toContain('not-an-email');
    expect(emailMessage('name@example.com')).toBeUndefined();
  });

  it('phoneMessage accepts Kenyan mobiles and explains digit counts', () => {
    expect(phoneMessage('')).toBeUndefined();
    expect(phoneMessage('', { required: true })).toContain('0712 345 678');
    expect(phoneMessage('abc')).toContain('Letters are not allowed');
    expect(phoneMessage('123')).toContain('You entered 3 digits');
    expect(phoneMessage('0712345678')).toBeUndefined();
    expect(phoneMessage('712345678')).toBeUndefined();
    expect(phoneMessage('+254712345678')).toBeUndefined();
  });

  it('personNameMessage requires a typed name with a minimum length', () => {
    expect(personNameMessage('')).toContain('Jane Wambua');
    expect(personNameMessage('A')).toContain('at least 2');
    expect(personNameMessage('Jane Wambua')).toBeUndefined();
  });

  it('dateMessage requires YYYY-MM-DD', () => {
    expect(dateMessage('')).toContain('2026-09-22');
    expect(dateMessage('22/09/2026')).toContain('YYYY-MM-DD');
    expect(dateMessage('2026-02-30')).toContain('real calendar');
    expect(dateMessage('2026-09-22')).toBeUndefined();
  });

  it('integerMessage and moneyMessage cover optional vs required', () => {
    expect(integerMessage('')).toBeUndefined();
    expect(integerMessage('', { required: true })).toContain('e.g. 3');
    expect(integerMessage('1.5')).toContain('whole number');
    expect(integerMessage('0', { min: 1, label: 'quantity' })).toContain('at least 1');
    expect(moneyMessage('', { required: false })).toBeUndefined();
    expect(moneyMessage('0', { allowZero: true })).toBeUndefined();
    expect(requiredChoiceMessage('')).toContain('Select a');
    expect(requiredChoiceMessage('cash')).toBeUndefined();
  });
});
