import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import SalesPersonReportView from './SalesPersonReportView';
import { reportsAPI, usersAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  reportsAPI: {
    salesByPerson: jest.fn(),
    salesByPersonCsv: jest.fn(),
    exportFile: jest.fn(),
  },
  usersAPI: {
    list: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../page', () => ({
  FilterBar: ({ children }) => <div>{children}</div>,
  FilterField: ({ label, children }) => (
    <div>
      {label ? <span>{label}</span> : null}
      {children}
    </div>
  ),
  PageLoading: () => <div>Loading…</div>,
  EmptyState: ({ title }) => <div>{title}</div>,
}));

const emptyReport = {
  period: '2026-07',
  period_display: 'July 2026',
  note: 'Test note',
  summary: {
    sales_count: 0,
    gross_sales: 0,
    refunds_total: 0,
    net_sales: 0,
  },
  staff: [],
};

describe('SalesPersonReportView period picker', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    usersAPI.list.mockResolvedValue({ data: { results: [] } });
    reportsAPI.salesByPerson.mockResolvedValue({ data: emptyReport });
  });

  it('requests report with period=month by default', async () => {
    render(<SalesPersonReportView />);

    await waitFor(() => {
      expect(reportsAPI.salesByPerson).toHaveBeenCalledWith({ period: 'month' });
    });
  });

  it('switches to period=today when Today tab is clicked', async () => {
    render(<SalesPersonReportView />);
    await waitFor(() => expect(reportsAPI.salesByPerson).toHaveBeenCalled());

    jest.clearAllMocks();
    reportsAPI.salesByPerson.mockResolvedValue({ data: emptyReport });

    const periodTabs = within(screen.getByRole('tablist', { name: 'Report period' }));
    fireEvent.click(periodTabs.getByRole('tab', { name: 'Today' }));

    await waitFor(() => {
      expect(reportsAPI.salesByPerson).toHaveBeenCalledWith({ period: 'today' });
    });
  });

  it('uses month param when a specific calendar month is picked', async () => {
    render(<SalesPersonReportView />);
    await waitFor(() => expect(reportsAPI.salesByPerson).toHaveBeenCalled());

    jest.clearAllMocks();
    reportsAPI.salesByPerson.mockResolvedValue({ data: emptyReport });

    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    fireEvent.change(screen.getByDisplayValue(currentMonth), {
      target: { value: '2026-06' },
    });

    await waitFor(() => {
      expect(reportsAPI.salesByPerson).toHaveBeenCalledWith({ month: '2026-06' });
    });
  });

  it('offers PDF, Excel, and CSV downloads for the current filters', async () => {
    reportsAPI.exportFile.mockResolvedValue('staff.pdf');
    render(<SalesPersonReportView />);
    await waitFor(() => expect(reportsAPI.salesByPerson).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith(
        'sales-by-person',
        { period: 'month' },
        'pdf'
      );
    });
    expect(screen.getByRole('button', { name: /Download Excel/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download CSV/i })).toBeInTheDocument();
  });
});
