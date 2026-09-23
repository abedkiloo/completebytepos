import React from 'react';
import { render, screen } from '@testing-library/react';
import SaleCorrectionCompare from './SaleCorrectionCompare';

describe('SaleCorrectionCompare', () => {
  it('explains void/refund vs rollback', () => {
    render(<SaleCorrectionCompare highlight="sale_refund" />);
    expect(screen.getByText(/Choose the right correction/i)).toBeInTheDocument();
    expect(screen.getByText(/Void or refund a sale/i)).toBeInTheDocument();
    expect(screen.getByText(/Roll back a mistaken sale/i)).toBeInTheDocument();
    expect(screen.getByText(/customer returns/i)).toBeInTheDocument();
  });
});
