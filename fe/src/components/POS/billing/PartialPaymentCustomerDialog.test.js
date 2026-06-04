import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PartialPaymentCustomerDialog from './PartialPaymentCustomerDialog';

describe('PartialPaymentCustomerDialog', () => {
  it('offers search and add customer actions', () => {
    const onSelectCustomer = jest.fn();
    const onAddCustomer = jest.fn();
    const onClose = jest.fn();

    render(
      <PartialPaymentCustomerDialog
        open
        canAddCustomer
        onSelectCustomer={onSelectCustomer}
        onAddCustomer={onAddCustomer}
        onClose={onClose}
      />
    );

    expect(screen.getByText(/Select a customer first/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Search customer/i }));
    expect(onSelectCustomer).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Add new customer/i }));
    expect(onAddCustomer).toHaveBeenCalled();
  });

  it('hides add customer when not allowed', () => {
    render(
      <PartialPaymentCustomerDialog
        open
        canAddCustomer={false}
        onSelectCustomer={jest.fn()}
        onClose={jest.fn()}
      />
    );

    expect(screen.queryByRole('button', { name: /Add new customer/i })).not.toBeInTheDocument();
  });
});
