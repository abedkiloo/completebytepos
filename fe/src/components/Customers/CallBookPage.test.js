import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CallBookPage from './CallBookPage';

jest.mock('../../services/api', () => ({
  customersAPI: {
    callBook: jest.fn(),
    markCall: jest.fn(),
    holdCall: jest.fn(),
    callBookPlan: jest.fn(),
    saveCallBookPlan: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  isManagerOrAdminFromStorage: () => false,
}));

const { customersAPI } = require('../../services/api');

const book = {
  summary: {
    week_start: '2026-11-16',
    week_end: '2026-11-20',
    is_call_day: true,
    weekday: 0,
    scope: 'today',
    callable: 2,
    called: 1,
    not_called: 1,
    cannot_call: 1,
    today_callable: 2,
    today_not_called: 1,
  },
  results: [
    {
      customer_id: 1,
      name: 'Not Called Shop',
      phone: '0718000001',
      county: 'Nairobi',
      sub_county: 'Starehe',
      ward: 'Landimawe',
      buyer_segment: 'at_risk',
      weekday: 0,
      called_this_week: false,
      outcome: '',
      request_summary: '',
      previous_summary: 'Ask about zippers next week',
      previous_outcome: 'ask_later',
      hold: null,
    },
    {
      customer_id: 2,
      name: 'Called Shop',
      phone: '0718000002',
      county: 'Nairobi',
      sub_county: 'Starehe',
      ward: 'Landimawe',
      buyer_segment: 'active',
      weekday: 0,
      called_this_week: true,
      outcome: 'called',
      request_summary: 'Wants webbing',
      previous_summary: '',
      hold: null,
    },
  ],
};

describe('CallBookPage', () => {
  beforeEach(() => {
    customersAPI.callBook.mockResolvedValue({ data: book });
    customersAPI.markCall.mockResolvedValue({ data: { called_this_week: true } });
    customersAPI.holdCall.mockResolvedValue({ data: { hold_minutes: 5 } });
  });

  test('shows who has not been called, the number, and the last request', async () => {
    render(<CallBookPage />);
    expect(await screen.findByText('Not Called Shop')).toBeInTheDocument();
    expect(screen.getByText('Called Shop')).toBeInTheDocument();
    expect(screen.getByText('0718000001').closest('a')).toHaveAttribute('href', 'tel:0718000001');
    expect(screen.getByText(/Ask about zippers next week/)).toBeInTheDocument();
    expect(screen.getByTestId('call-book-counts')).toHaveTextContent('Called 1 of 2');
    const names = screen.getAllByText(/Shop/).map((node) => node.textContent);
    expect(names[0]).toBe('Not Called Shop');
  });

  test('marks ask later as called for this week', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.selectOptions(screen.getByLabelText('Outcome for Not Called Shop'), 'ask_later');
    await userEvent.clear(screen.getByLabelText('Request for Not Called Shop'));
    await userEvent.type(screen.getByLabelText('Request for Not Called Shop'), 'Call Thursday');
    await userEvent.click(screen.getByRole('button', { name: 'Mark called' }));
    await waitFor(() => {
      expect(customersAPI.markCall).toHaveBeenCalledWith(1, {
        outcome: 'ask_later',
        request_summary: 'Call Thursday',
      });
    });
  });

  test('weekend book does not offer a mark', async () => {
    customersAPI.callBook.mockResolvedValue({
      data: {
        ...book,
        summary: { ...book.summary, is_call_day: false, today_not_called: 1 },
      },
    });
    render(<CallBookPage />);
    expect(await screen.findByText(/Marking opens again on Monday/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Mark called' })).not.toBeInTheDocument();
  });
});
