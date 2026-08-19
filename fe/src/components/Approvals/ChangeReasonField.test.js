import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ChangeReasonField from './ChangeReasonField';

describe('ChangeReasonField', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'manager', custom_role: { name: 'Manager' } })
    );
  });

  it('shows approval guidance for managers', () => {
    render(
      <ChangeReasonField context="role_permissions" value="" onChange={() => {}} />
    );
    expect(screen.getByText(/Manager approval required/i)).toBeInTheDocument();
    expect(screen.getByText(/permission updates require manager approval/i)).toBeInTheDocument();
    expect(screen.getByText(/Pending approvals/i)).toBeInTheDocument();
  });

  it('shows queue message for non-checkers', () => {
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', custom_role: { name: 'Sales Personnel' } })
    );
    render(<ChangeReasonField value="" onChange={() => {}} />);
    expect(screen.getByText(/manager or admin will review/i)).toBeInTheDocument();
  });

  it('allows a 5-character stock reason', () => {
    render(<ChangeReasonField context="stock" value="Count" onChange={() => {}} />);
    const input = screen.getByLabelText(/Reason for this stock change/i);
    expect(input).toHaveValue('Count');
    expect(input).toHaveAttribute('minLength', '5');
    expect(screen.getByText(/At least 5 characters/)).toBeInTheDocument();
  });

  it('renders a plain hint when approval is not required', () => {
    const onChange = jest.fn();
    render(
      <ChangeReasonField
        value="ok"
        onChange={onChange}
        requiresApproval={false}
        hint="Optional note"
        error="Too short"
      />
    );
    expect(screen.queryByText(/Manager approval required/i)).not.toBeInTheDocument();
    expect(screen.getByText('Optional note')).toBeInTheDocument();
    expect(screen.getByText('Too short')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Reason for this change/i), {
      target: { value: 'Count' },
    });
    expect(onChange).toHaveBeenCalledWith('Count');
  });

  it('omits the hint block when approval is off and no hint is given', () => {
    render(
      <ChangeReasonField
        value=""
        onChange={() => {}}
        requiresApproval={false}
        hint=""
        required={false}
        minLength={8}
      />
    );
    expect(screen.queryByText(/Manager approval required/i)).not.toBeInTheDocument();
    expect(screen.getByText(/At least 8 characters/)).toBeInTheDocument();
  });
});
