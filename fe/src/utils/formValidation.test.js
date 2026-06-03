import {
  required,
  minLength,
  normalizeApiErrors,
  hasValidationErrors,
  firstErrorField,
  fieldError,
  formGroupClass,
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

  it('normalizeApiErrors flattens nested objects', () => {
    expect(
      normalizeApiErrors({ profile: { phone_number: ['Required'] } })
    ).toMatchObject({
      'profile.phone_number': 'Required',
      phone_number: 'Required',
    });
  });

  it('required allows non-string values', () => {
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
    expect(minLength('abc', 6)).toContain('6');
    expect(minLength('abcdef', 6)).toBeUndefined();
  });

  it('fieldError reads nested profile keys', () => {
    expect(fieldError({ 'profile.phone_number': 'bad' }, 'phone_number')).toBe('bad');
  });

  it('formGroupClass marks invalid fields', () => {
    expect(formGroupClass({ email: 'invalid' }, 'email')).toContain('has-error');
    expect(formGroupClass({}, 'email')).not.toContain('has-error');
  });
});
