import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import PayrollPage from './PayrollPage';
import { payrollAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  payrollAPI: {
    listRuns: jest.fn(),
    listComponents: jest.fn(),
    seedComponents: jest.fn(),
    updateComponent: jest.fn(),
    getSettings: jest.fn(),
    myPayslips: jest.fn(),
    createRun: jest.fn(),
    calculateRun: jest.fn(),
    submitRun: jest.fn(),
    approveRun: jest.fn(),
    rejectRun: jest.fn(),
    cancelRun: jest.fn(),
    runPayslips: jest.fn(),
    runSummary: jest.fn(),
    updateSettings: jest.fn(),
    payslipPdf: jest.fn(),
    myPayslipPdf: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe('PayrollPage', () => {
  beforeEach(() => {
    payrollAPI.listRuns.mockResolvedValue({ data: { results: [] } });
    payrollAPI.listComponents.mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            code: 'BASIC',
            name: 'Basic salary',
            kind: 'earning',
            calculation_type: 'fixed',
            is_statutory: false,
            is_active: true,
          },
        ],
      },
    });
    payrollAPI.getSettings.mockResolvedValue({
      data: {
        currency: 'KES',
        pay_day: 28,
        statutory_enabled: false,
        include_appraisal_bonus: true,
        letterhead_line: '',
      },
    });
    payrollAPI.myPayslips.mockResolvedValue({ data: [] });
  });

  test('renders payroll header and tabs', async () => {
    render(<PayrollPage />);
    expect(await screen.findByText('Payroll')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /New run/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(payrollAPI.listRuns).toHaveBeenCalled();
    });
  });
});
