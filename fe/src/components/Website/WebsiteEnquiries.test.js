import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import WebsiteEnquiries from './WebsiteEnquiries';
import { cmsAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  cmsAPI: {
    listEnquiries: jest.fn(),
    updateEnquiry: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('../../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (v) => v,
}));

const ROWS = [
  {
    id: 11,
    name: 'Amina',
    phone: '0718515142',
    business: 'Upholsterer',
    location: 'Nairobi',
    interest: 'No. 5 zipper',
    quantity: '20 metres',
    message: 'For cushions',
    product_name: 'No. 5 nylon zipper',
    status: 'new',
    created_at: '2026-11-24T10:00:00Z',
  },
  {
    id: 12,
    name: 'Brian',
    phone: '0718000001',
    business: '',
    location: '',
    interest: 'Webbing',
    quantity: '4 rolls',
    message: '',
    product_name: null,
    status: 'reviewed',
    created_at: '2026-11-23T09:00:00Z',
  },
];

describe('WebsiteEnquiries', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cmsAPI.listEnquiries.mockResolvedValue({ data: { results: ROWS } });
    cmsAPI.updateEnquiry.mockResolvedValue({ data: { ...ROWS[0], status: 'reviewed' } });
  });

  it('unit: lists phone, items and amount for follow-up', async () => {
    render(<WebsiteEnquiries />);
    expect(await screen.findByText('Amina')).toBeInTheDocument();
    expect(screen.getByText('0718515142')).toBeInTheDocument();
    expect(screen.getByText('20 metres')).toBeInTheDocument();
    expect(screen.getByText('No. 5 zipper')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Amount' })).toBeInTheDocument();
  });

  it('corrected: empty inbox explains follow-up purpose', async () => {
    cmsAPI.listEnquiries.mockResolvedValue({ data: { results: [] } });
    render(<WebsiteEnquiries />);
    expect(await screen.findByText('No enquiries in this view')).toBeInTheDocument();
    expect(
      screen.getByText(/When someone sends a request from the website, it appears here/),
    ).toBeInTheDocument();
  });

  it('integration: filters by status and search', async () => {
    render(<WebsiteEnquiries />);
    await screen.findByText('Amina');
    fireEvent.click(screen.getByRole('button', { name: 'Reviewed' }));
    await waitFor(() =>
      expect(cmsAPI.listEnquiries).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'reviewed' }),
      ),
    );
    fireEvent.change(screen.getByPlaceholderText(/Search name, phone or fitting/), {
      target: { value: 'zip' },
    });
    await waitFor(() =>
      expect(cmsAPI.listEnquiries).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'zip' }),
      ),
    );
  });

  it('module: mark reviewed and close update status via API', async () => {
    render(<WebsiteEnquiries />);
    const row = (await screen.findByText('Amina')).closest('tr');
    fireEvent.click(within(row).getByRole('button', { name: 'Mark reviewed' }));
    await waitFor(() =>
      expect(cmsAPI.updateEnquiry).toHaveBeenCalledWith(11, { status: 'reviewed' }),
    );
    expect(toast.success).toHaveBeenCalledWith('Marked as reviewed');

    const reviewedRow = (await screen.findByText('Brian')).closest('tr');
    fireEvent.click(within(reviewedRow).getByRole('button', { name: 'Close' }));
    await waitFor(() =>
      expect(cmsAPI.updateEnquiry).toHaveBeenCalledWith(12, { status: 'closed' }),
    );
  });

  it('security: load failure surfaces toast and does not invent rows', async () => {
    cmsAPI.listEnquiries.mockRejectedValue({ response: { data: { detail: 'Forbidden' } } });
    render(<WebsiteEnquiries />);
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.queryByText('Amina')).not.toBeInTheDocument();
  });

  it('stress: renders a large enquiry inbox without throwing', async () => {
    const many = Array.from({ length: 120 }, (_, i) => ({
      ...ROWS[0],
      id: i + 1,
      name: `Buyer ${i}`,
      phone: `0718${String(i).padStart(6, '0')}`,
      quantity: `${i + 1} m`,
    }));
    cmsAPI.listEnquiries.mockResolvedValue({ data: { results: many } });
    render(<WebsiteEnquiries />);
    expect(await screen.findByText('Buyer 0')).toBeInTheDocument();
    expect(screen.getByText('Buyer 119')).toBeInTheDocument();
    expect(screen.getByText('120 m')).toBeInTheDocument();
  });
});
