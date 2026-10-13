import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import KenyaLocationFields from './KenyaLocationFields';

jest.mock('../../hooks/useKenyaAdminUnits', () => ({
  useKenyaAdminUnits: () => ({
    loading: false,
    defaults: { county: 'Nairobi', sub_county: 'Starehe', ward: 'Landimawe' },
    counties: {
      Nairobi: {
        Starehe: ['Landimawe', 'Nairobi Central'],
        Westlands: ['Kitisuru', 'Parklands'],
      },
      Kiambu: {
        'Thika Town': ['Hospital', 'Kamenu'],
      },
    },
  }),
  kenyaSubCounties: (counties, county) =>
    county && counties[county] ? Object.keys(counties[county]).sort() : [],
  kenyaWards: (counties, county, sub) =>
    county && sub && counties[county]?.[sub] ? [...counties[county][sub]].sort() : [],
}));

jest.mock('../Shared/SearchableSelect', () => ({
  __esModule: true,
  default: ({ name, value, onChange, options, disabled }) => (
    <select
      aria-label={name}
      data-testid={name}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange({ target: { value: e.target.value } })}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  ),
}));

describe('KenyaLocationFields', () => {
  it('cascades county → sub-county → ward in one patch (same as app)', () => {
    const onChange = jest.fn();
    render(
      <KenyaLocationFields
        formData={{
          county: 'Nairobi',
          sub_county: 'Starehe',
          ward: 'Landimawe',
          city: 'Nairobi',
          address: '',
        }}
        formErrors={{}}
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getByTestId('cust-county'), { target: { value: 'Kiambu' } });

    expect(onChange).toHaveBeenCalledWith({
      county: 'Kiambu',
      sub_county: 'Thika Town',
      ward: 'Hospital',
      city: 'Kiambu',
    });
  });

  it('keeps location name editable without clearing county selection', () => {
    const onChange = jest.fn();
    render(
      <KenyaLocationFields
        formData={{
          county: 'Nairobi',
          sub_county: 'Starehe',
          ward: 'Landimawe',
          city: 'Nairobi',
          address: '',
        }}
        formErrors={{}}
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getByLabelText(/Location name/i), {
      target: { value: 'Gikomba' },
    });
    expect(onChange).toHaveBeenCalledWith('address', 'Gikomba');
  });

  it('resets ward when sub-county changes', async () => {
    const onChange = jest.fn();
    render(
      <KenyaLocationFields
        formData={{
          county: 'Nairobi',
          sub_county: 'Starehe',
          ward: 'Landimawe',
          city: 'Nairobi',
          address: '',
        }}
        formErrors={{}}
        onChange={onChange}
      />
    );

    fireEvent.change(screen.getByTestId('cust-sub-county'), {
      target: { value: 'Westlands' },
    });

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith({
        sub_county: 'Westlands',
        ward: 'Kitisuru',
      });
    });
  });
});
