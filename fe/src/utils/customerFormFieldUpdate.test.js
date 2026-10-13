import { applyCustomerFormFieldUpdate } from './customerFormFieldUpdate';

describe('applyCustomerFormFieldUpdate', () => {
  it('updates a single field', () => {
    expect(applyCustomerFormFieldUpdate({ county: 'Nairobi' }, 'ward', 'Landimawe')).toEqual({
      county: 'Nairobi',
      ward: 'Landimawe',
    });
  });

  it('applies a county cascade patch atomically', () => {
    const prev = {
      county: 'Nairobi',
      sub_county: 'Starehe',
      ward: 'Landimawe',
      city: 'Nairobi',
      address: 'Gikomba',
    };
    expect(
      applyCustomerFormFieldUpdate(prev, {
        county: 'Kiambu',
        sub_county: 'Thika Town',
        ward: 'Hospital',
        city: 'Kiambu',
      })
    ).toEqual({
      county: 'Kiambu',
      sub_county: 'Thika Town',
      ward: 'Hospital',
      city: 'Kiambu',
      address: 'Gikomba',
    });
  });
});
