import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { CustomerPicker } from '../POS/v2/CustomerPicker';
import { customersAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  customersAPI: { list: jest.fn() },
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

describe('CustomerPicker server search', () => {
  beforeEach(() => {
    customersAPI.list.mockReset();
    customersAPI.list.mockResolvedValue({
      data: {
        results: [
          { id: 9, name: 'Jane Hardware', phone: '+254712345678', customer_code: 'C9' },
        ],
      },
    });
  });

  it('searches the server so customers beyond the first page are found', async () => {
    render(<CustomerPicker onSelect={jest.fn()} requireCustomer />);
    fireEvent.click(screen.getByText('Select customer'));
    fireEvent.change(screen.getByPlaceholderText(/Search duka, owner, contact/i), {
      target: { value: '0712345678' },
    });
    await waitFor(() =>
      expect(customersAPI.list).toHaveBeenCalledWith(
        expect.objectContaining({ search: '0712345678', is_active: true })
      )
    );
    expect(await screen.findByText('Jane Hardware')).toBeInTheDocument();
  });
});
