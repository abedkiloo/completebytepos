import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SetupGate from './SetupGate';
import { fetchSetupStatus, getCachedSetupStatus } from '../../utils/setupStatus';

jest.mock('../../utils/setupStatus', () => ({
  fetchSetupStatus: jest.fn(),
  getCachedSetupStatus: jest.fn(() => null),
}));

describe('SetupGate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getCachedSetupStatus.mockReturnValue(null);
  });

  it('keeps the app up when setup-status is blocked by password change', async () => {
    fetchSetupStatus.mockRejectedValue({
      response: { data: { error: 'password_change_required' } },
    });
    render(
      <SetupGate>
        <p>Change password screen</p>
      </SetupGate>
    );
    expect(await screen.findByText('Change password screen')).toBeInTheDocument();
    expect(screen.queryByText('Cannot reach the server')).not.toBeInTheDocument();
  });

  it('uses cached setup status instead of hanging the app', async () => {
    getCachedSetupStatus.mockReturnValue({ installed: true, needs_install: false });
    fetchSetupStatus.mockRejectedValue(new Error('timeout'));
    render(
      <SetupGate>
        <p>App ready</p>
      </SetupGate>
    );
    expect(await screen.findByText('App ready')).toBeInTheDocument();
  });

  it('shows a retry action when the API never responds', async () => {
    fetchSetupStatus.mockRejectedValue(new Error('timeout'));
    render(
      <SetupGate>
        <p>App ready</p>
      </SetupGate>
    );

    expect(await screen.findByText('Cannot reach the server')).toBeInTheDocument();
    fetchSetupStatus.mockResolvedValueOnce({ installed: true, needs_install: false });
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => {
      expect(screen.getByText('App ready')).toBeInTheDocument();
    });
  });
});
