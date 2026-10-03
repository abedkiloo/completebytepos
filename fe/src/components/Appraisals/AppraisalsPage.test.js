import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import AppraisalsPage from './AppraisalsPage';
import { appraisalsAPI } from '../../services/api';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';

jest.mock('../../services/api', () => ({
  appraisalsAPI: {
    me: jest.fn(),
    team: jest.fn(),
    savePolicy: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
  hasPermission: jest.fn(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

describe('AppraisalsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getStoredAuth.mockReturnValue({ permissions: [{ module: 'appraisals', action: 'manage' }] });
    hasPermission.mockReturnValue(true);
  });

  it('hides personal progress for admins who have no target', async () => {
    appraisalsAPI.me.mockResolvedValue({
      data: {
        has_personal_target: false,
        policy: {
          daily_target: 20000,
          manager_daily_target: 35000,
          role_daily_targets: {
            Manager: 35000,
            'Sales Personnel': 20000,
            'Field Sales': 20000,
          },
          daily_star_bands: [{ min: 0, stars: 1, label: '' }],
          monthly_bonus_bands: [{ min: 0, stars: 1, bonus: 0, label: '' }],
          daily_tip_packs: [],
        },
      },
    });
    appraisalsAPI.team.mockResolvedValue({ data: { results: [] } });

    render(<AppraisalsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Admin accounts are not scored/)).toBeInTheDocument();
    });
    expect(screen.queryByRole('tab', { name: /My progress/i })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Team/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Template/i })).toBeInTheDocument();
  });
});
