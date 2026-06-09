import React from 'react';
import { render, screen } from '@testing-library/react';
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
});
