import { formBannerMessage } from './formFeedback';

describe('formBannerMessage', () => {
  it('returns null for empty', () => {
    expect(formBannerMessage(null)).toBeNull();
    expect(formBannerMessage({})).toBeNull();
  });

  it('prefers _form', () => {
    expect(formBannerMessage({ _form: 'Denied', name: 'Required' })).toBe('Denied');
  });

  it('summarises field-only errors without duplicating field text', () => {
    expect(formBannerMessage({ name: 'Required', phone: 'Invalid' })).toBe(
      'Please fix the highlighted fields below.'
    );
  });
});
