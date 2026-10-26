import {
  customerFormFromRecord,
  customerSavePayload,
  validateCustomerForm,
} from './customerFormState';

describe('customerFormState', () => {
  it('maps a customer record into the editor form', () => {
    const form = customerFormFromRecord({
      name: 'Wambua Hardware',
      owner_name: 'Jane',
      phone: '0712345678',
      gender: 'female',
      typical_goods: ['cement'],
    });
    expect(form.name).toBe('Wambua Hardware');
    expect(form.owner_name).toBe('Jane');
    expect(form.gender).toBe('female');
    expect(form.typical_goods).toEqual(['cement']);
    expect(customerSavePayload(form).phone).toBe('0712345678');
    expect(customerSavePayload(form).gender).toBe('female');
  });

  it('requires a duka name', () => {
    expect(validateCustomerForm({ name: '' }).name).toBeTruthy();
  });

  it('requires gender only when registering a new customer', () => {
    expect(validateCustomerForm({ name: 'Wambua Hardware' }, { requireGender: true }).gender).toBeTruthy();
    expect(validateCustomerForm({ name: 'Wambua Hardware', gender: '' }, { requireGender: false }).gender).toBeFalsy();
    expect(
      validateCustomerForm({ name: 'Wambua Hardware', gender: 'male' }, { requireGender: true }).gender
    ).toBeFalsy();
  });
});
