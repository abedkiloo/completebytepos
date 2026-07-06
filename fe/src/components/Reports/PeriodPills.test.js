import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PeriodPills from './PeriodPills';

describe('PeriodPills', () => {
  it('renders all report period tabs', () => {
    render(<PeriodPills value="month" onChange={jest.fn()} />);

    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'This week' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'This month' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'This year' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'This month' })).toHaveAttribute('aria-selected', 'true');
  });

  it('calls onChange when a period tab is clicked', () => {
    const onChange = jest.fn();
    render(<PeriodPills value="month" onChange={onChange} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Today' }));
    expect(onChange).toHaveBeenCalledWith('today');

    fireEvent.click(screen.getByRole('tab', { name: 'This year' }));
    expect(onChange).toHaveBeenCalledWith('year');
  });
});
