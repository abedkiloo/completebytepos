import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SetupGate from './SetupGate';
import { fetchSetupStatus } from '../../utils/setupStatus';

jest.mock('../../utils/setupStatus', () => ({
  fetchSetupStatus: jest.fn(),
}));

describe('SetupGate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
