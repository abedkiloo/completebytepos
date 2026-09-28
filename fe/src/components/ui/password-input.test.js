import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { PasswordInput } from './password-input';

describe('PasswordInput', () => {
  it('hides the value until the toggle is pressed', () => {
    render(<PasswordInput id="secret" aria-label="Password" defaultValue="s3cret" />);

    const field = screen.getByLabelText(/^password$/i);
    expect(field).toHaveAttribute('type', 'password');
    expect(screen.getByRole('button', { name: /show password/i })).toHaveAttribute(
      'aria-pressed',
      'false'
    );

    fireEvent.click(screen.getByRole('button', { name: /show password/i }));
    expect(field).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: /hide password/i })).toHaveAttribute(
      'aria-pressed',
      'true'
    );

    fireEvent.click(screen.getByRole('button', { name: /hide password/i }));
    expect(field).toHaveAttribute('type', 'password');
  });

  it('does not toggle while disabled', () => {
    render(<PasswordInput aria-label="Password" disabled />);
    fireEvent.click(screen.getByRole('button', { name: /show password/i }));
    expect(screen.getByLabelText(/^password$/i)).toHaveAttribute('type', 'password');
  });
});
