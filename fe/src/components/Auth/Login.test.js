import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import Login from './Login';
import { fetchSetupStatus } from '../../utils/setupStatus';
import { authAPI } from '../../services/api';

jest.mock('../../utils/setupStatus', () => ({
  fetchSetupStatus: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  authAPI: { login: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  persistMeResponse: jest.fn(),
}));

describe('Login landing', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    fetchSetupStatus.mockResolvedValue({ installed: true, needs_install: false });
  });

  it('shows the product landing beside the sign-in form', async () => {
    render(<Login />);

    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByTestId('login-landing')).toBeInTheDocument();
    expect(
      screen.getAllByText(/run the counter, the stock, and the close/i).length
    ).toBeGreaterThan(0);
    expect(await screen.findByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getAllByText('Omuwenga Suppliers').length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^sign in$/i })).toBeDisabled();
  });

  it('enables submit once username and password are filled', async () => {
    render(<Login />);
    const username = await screen.findByLabelText(/username/i);
    const password = screen.getByLabelText(/^password$/i);

    fireEvent.change(username, { target: { value: 'cashier1' } });
    fireEvent.change(password, { target: { value: 'secret' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^sign in$/i })).toBeEnabled();
    });
    expect(authAPI.login).not.toHaveBeenCalled();
  });
});
