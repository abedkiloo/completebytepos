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
      typical_goods: ['cement'],
    });
    expect(form.name).toBe('Wambua Hardware');
    expect(form.owner_name).toBe('Jane');
    expect(form.typical_goods).toEqual(['cement']);
    expect(customerSavePayload(form).phone).toBe('0712345678');
  });

  it('requires a duka name', () => {
    expect(validateCustomerForm({ name: '' }).name).toBeTruthy();
  });
});
