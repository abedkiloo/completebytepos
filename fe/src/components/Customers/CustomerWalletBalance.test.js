import React from 'react';
import { render, screen } from '@testing-library/react';
import { CustomerWalletBalance } from './CustomerWalletBalance';

describe('CustomerWalletBalance', () => {
  it('renders debt in destructive tone', () => {
    render(<CustomerWalletBalance balance="-50" />);
    expect(screen.getByText(/owed/i)).toHaveClass('text-destructive');
  });

  it('renders credit in green tone', () => {
    render(<CustomerWalletBalance balance="30" />);
    expect(screen.getByText(/credit/i)).toHaveClass('text-emerald-600');
  });

  it('renders dash for zero by default', () => {
    render(<CustomerWalletBalance balance="0" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
