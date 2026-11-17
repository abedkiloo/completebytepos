import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
    scope: 'week',
    callable: 2,
    called: 1,
    not_called: 1,
    cannot_call: 1,
    follow_ups: 0,
    today_callable: 2,
    today_not_called: 1,
    days: [
      { weekday: 0, callable: 2, called: 1, not_called: 1 },
      { weekday: 1, callable: 0, called: 0, not_called: 0 },
      { weekday: 2, callable: 0, called: 0, not_called: 0 },
      { weekday: 3, callable: 0, called: 0, not_called: 0 },
      { weekday: 4, callable: 0, called: 0, not_called: 0 },
    ],
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
      follow_up_on: '',
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
      follow_up_on: '',
      hold: null,
    },
  ],
};

describe('CallBookPage', () => {
  beforeEach(() => {
    customersAPI.callBook.mockResolvedValue({ data: book });
    customersAPI.markCall.mockResolvedValue({ data: { called_this_week: true } });
    customersAPI.holdCall.mockResolvedValue({ data: { hold_minutes: 5 } });
    Object.assign(navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  test('shows the next customer and copies the number instead of dialling', async () => {
    render(<CallBookPage />);
    expect(await screen.findByText('Not Called Shop')).toBeInTheDocument();
    expect(screen.queryByText('Called Shop')).not.toBeInTheDocument();
    expect(screen.getByText('0718000001')).toBeInTheDocument();
    expect(document.querySelector('a[href^="tel:"]')).toBeNull();
    expect(screen.getAllByText(/Ask about zippers next week/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Copy phone number' }));
    await waitFor(() => {
      expect(customersAPI.holdCall).toHaveBeenCalledWith(1);
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('0718000001');
    });
  });

  test('records call later with the note', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('button', { name: 'Call later' }));
    await userEvent.clear(screen.getByLabelText('Notes for Not Called Shop'));
    await userEvent.type(screen.getByLabelText('Notes for Not Called Shop'), 'Call Thursday');
    fireEvent.change(screen.getByLabelText('Time to call Not Called Shop'), {
      target: { value: '15:30' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Save record' }));
    await waitFor(() => {
      expect(customersAPI.markCall).toHaveBeenCalledWith(1, {
        outcome: 'ask_later',
        request_summary: 'Call Thursday',
        follow_up_on: '',
        follow_up_time: '15:30',
      });
    });
  });

  test('asks for a time before saving call later', async () => {
    const { toast } = require('../../utils/toast');
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('button', { name: 'Call later' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save record' }));
    expect(toast.error).toHaveBeenCalledWith('Choose the time to call again.');
    expect(customersAPI.markCall).not.toHaveBeenCalled();
  });

  test('shows a due call-later customer first on load', async () => {
    customersAPI.callBook.mockResolvedValue({
      data: {
        ...book,
        results: [
          {
            ...book.results[0],
            customer_id: 9,
            name: 'Due Shop',
            called_this_week: true,
            outcome: 'ask_later',
            weekday: 3,
            call_later_due: true,
            follow_up_at: '2026-11-16T09:00:00+03:00',
          },
          ...book.results,
        ],
      },
    });
    render(<CallBookPage />);
    expect(await screen.findByText('Due Shop')).toBeInTheDocument();
    expect(screen.getByText('The time to call again has been reached.')).toBeInTheDocument();
    expect(screen.queryByText('Not Called Shop')).not.toBeInTheDocument();
  });

  test('weekend book does not offer a record', async () => {
    customersAPI.callBook.mockResolvedValue({
      data: {
        ...book,
        summary: { ...book.summary, is_call_day: false, weekday: 5 },
      },
    });
    render(<CallBookPage />);
    expect(await screen.findByText(/Recording opens again on Monday/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save record' })).not.toBeInTheDocument();
  });

  test('opens the call form when a customer on the week list is clicked', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('tab', { name: 'Weekly schedule' }));
    expect(screen.queryByRole('button', { name: 'Save record' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Not Called Shop/ }));
    expect(screen.getByRole('button', { name: 'Save record' })).toBeInTheDocument();
    expect(screen.getByText('0718000001')).toBeInTheDocument();
  });

  test('overview uses the week counts', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('tab', { name: 'Overview' }));
    expect(screen.getByTestId('call-book-counts')).toHaveTextContent('Scheduled this week');
    expect(screen.getByTestId('call-book-counts')).toHaveTextContent('2');
  });

  test('drops a customer from the list after the call is recorded', async () => {
    let loads = 0;
    customersAPI.callBook.mockImplementation(() => {
      loads += 1;
      if (loads === 1) return Promise.resolve({ data: book });
      return Promise.resolve({ data: { ...book, count: 0, results: [] } });
    });
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('button', { name: 'Save record' }));
    expect(await screen.findByText(/already has a result/)).toBeInTheDocument();
    expect(screen.queryByText('Not Called Shop')).not.toBeInTheDocument();
  });

  test('pages the day list ten at a time', async () => {
    customersAPI.callBook.mockImplementation((params) => Promise.resolve({
      data: {
        ...book,
        count: 25,
        results: params.page === 2
          ? [{ ...book.results[0], customer_id: 50, name: 'Page Two Shop', called_this_week: false }]
          : [book.results[0]],
      },
    }));
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('tab', { name: 'Weekly schedule' }));
    expect(screen.getByText(/25 still to call/)).toBeInTheDocument();
    expect(screen.queryByText('Called Shop')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(await screen.findByText('Page Two Shop')).toBeInTheDocument();
    expect(customersAPI.callBook).toHaveBeenLastCalledWith(expect.objectContaining({
      status: 'not_called',
      page: 2,
      page_size: 10,
    }));
  });
});
