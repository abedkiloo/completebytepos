import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import PayrollPage from './PayrollPage';
import { payrollAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  payrollAPI: {
    listRuns: jest.fn(),
    getSettings: jest.fn(),
    listComponents: jest.fn(),
    myPayslips: jest.fn(),
    myPay: jest.fn(),
    updateSettings: jest.fn(),
  },
}));

jest.mock('../../utils/moduleFeatures', () => ({
  isModuleEnabled: () => true,
  isModuleFeatureEnabled: () => true,
}));

describe('PayrollPage mid-join proration settings', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(
      'permissions',
      JSON.stringify([
        { module: 'payroll', action: 'view', name: 'payroll.view' },
        { module: 'payroll', action: 'manage', name: 'payroll.manage' },
      ])
    );
    localStorage.setItem('user', JSON.stringify({ is_superuser: true }));
    localStorage.setItem('profile', JSON.stringify({ role: 'super_admin' }));
    payrollAPI.listRuns.mockResolvedValue({ data: [] });
    payrollAPI.listComponents.mockResolvedValue({ data: { results: [] } });
    payrollAPI.myPayslips.mockResolvedValue({ data: [] });
    payrollAPI.myPay.mockResolvedValue({ data: { linked: false } });
    payrollAPI.getSettings.mockResolvedValue({
      data: {
        currency: 'KES',
        pay_day: 28,
        prorate_mid_join: true,
        min_month_days: 28,
        statutory_enabled: false,
        include_appraisal_bonus: true,
        include_sales_commission: true,
        sales_commission_template: { scheme: 'daily_bands', bands: [] },
        letterhead_line: '',
      },
    });
  });

  it('shows mid-join proration controls on settings tab', async () => {
    render(<PayrollPage />);
    const settingsTab = await screen.findByRole('button', { name: /settings/i });
    settingsTab.click();
    await waitFor(() => {
      expect(screen.getByTestId('prorate-mid-join')).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Prorate salary when an employee joins mid-month/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Minimum month days/i)).toHaveValue(28);
  });
});
