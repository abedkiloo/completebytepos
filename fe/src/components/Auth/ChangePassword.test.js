import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ChangePassword from './ChangePassword';
import { authAPI, usersAPI } from '../../services/api';
import { persistMeResponse } from '../../utils/roleAccess';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('../../__mocks__/react-router-dom'),
  useNavigate: () => mockNavigate,
}));

jest.mock('../../services/api', () => ({
  authAPI: { me: jest.fn() },
  usersAPI: { changePassword: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  persistMeResponse: jest.fn(),
}));

jest.mock('../../utils/authSession', () => ({
  logoutLocally: jest.fn().mockResolvedValue(undefined),
}));

describe('ChangePassword', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.setItem('user', JSON.stringify({ id: 7, username: 'cashier1' }));
    localStorage.setItem(
      'profile',
      JSON.stringify({ role: 'cashier', must_change_password: true })
    );
  });

  it('saves a new password and continues', async () => {
    usersAPI.changePassword.mockResolvedValue({ data: { message: 'ok' } });
    authAPI.me.mockResolvedValue({
      data: {
        user: { id: 7, username: 'cashier1' },
        profile: { must_change_password: false },
      },
    });

    render(<ChangePassword />);

    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'ownpass1' },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: 'ownpass1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save password and continue/i }));

    await waitFor(() => {
      expect(usersAPI.changePassword).toHaveBeenCalledWith(7, 'ownpass1');
    });
    expect(persistMeResponse).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
  });

  it('rejects mismatched passwords', async () => {
    render(<ChangePassword />);
    fireEvent.change(screen.getByLabelText(/new password/i), {
      target: { value: 'ownpass1' },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: 'otherpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save password and continue/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i);
    expect(usersAPI.changePassword).not.toHaveBeenCalled();
  });
});
