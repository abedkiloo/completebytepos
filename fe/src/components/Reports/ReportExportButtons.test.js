import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReportExportButtons from './ReportExportButtons';
import { reportsAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  reportsAPI: {
    exportFile: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe('ReportExportButtons', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    reportsAPI.exportFile.mockResolvedValue('sales_2026-08-17.pdf');
  });

  it('renders PDF, Excel, and CSV for a known report', () => {
    render(<ReportExportButtons slug="sales" params={{ period: 'month' }} />);
    expect(screen.getByRole('button', { name: /Download PDF/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Excel/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download CSV/i })).toBeInTheDocument();
  });

  it('does not render for an unknown report slug', () => {
    const { container } = render(<ReportExportButtons slug="not-a-report" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('downloads PDF for the current filters', async () => {
    render(<ReportExportButtons slug="sales" params={{ date_from: '2026-08-01' }} />);
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith(
        'sales',
        { date_from: '2026-08-01' },
        'pdf'
      );
    });
    expect(toast.success).toHaveBeenCalledWith('PDF downloaded');
  });

  it('downloads Excel', async () => {
    render(<ReportExportButtons slug="expense" />);
    fireEvent.click(screen.getByRole('button', { name: /Download Excel/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith('expense', {}, 'xlsx');
    });
    expect(toast.success).toHaveBeenCalledWith('Excel downloaded');
  });

  it('downloads CSV', async () => {
    render(<ReportExportButtons slug="sales" />);
    fireEvent.click(screen.getByRole('button', { name: /Download CSV/i }));
    await waitFor(() => {
      expect(reportsAPI.exportFile).toHaveBeenCalledWith('sales', {}, 'csv');
    });
    expect(toast.success).toHaveBeenCalledWith('CSV downloaded');
  });

  it('uses a fallback error when the failure has no message', async () => {
    reportsAPI.exportFile.mockRejectedValueOnce({});
    render(<ReportExportButtons slug="sales" />);
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Could not download report');
    });
  });

  it('shows an error toast when export fails', async () => {
    reportsAPI.exportFile.mockRejectedValueOnce(new Error('Server down'));
    render(<ReportExportButtons slug="sales" />);
    fireEvent.click(screen.getByRole('button', { name: /Download CSV/i }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Server down');
    });
  });

  it('disables buttons while a download is in flight', async () => {
    let resolveDownload;
    reportsAPI.exportFile.mockImplementation(
      () => new Promise((resolve) => { resolveDownload = resolve; })
    );
    render(<ReportExportButtons slug="sales" />);
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/i }));
    expect(await screen.findByText('Downloading…')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Excel/i })).toBeDisabled();
    resolveDownload('ok');
    await waitFor(() => {
      expect(screen.queryByText('Downloading…')).not.toBeInTheDocument();
    });
  });

  it('honours the disabled prop', () => {
    render(<ReportExportButtons slug="sales" disabled />);
    expect(screen.getByRole('button', { name: /Download PDF/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Download Excel/i })).toBeDisabled();
  });
});
