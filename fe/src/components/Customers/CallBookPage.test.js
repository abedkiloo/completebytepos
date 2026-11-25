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
    callBookDayLog: jest.fn(),
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
    missed_last_week: 1,
    today_callable: 2,
    today_not_called: 1,
    days: [
      { weekday: 0, callable: 2, called: 1, not_called: 1, sub_counties: ['Starehe'] },
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
      missed_last_week: true,
      callers_this_week: [],
      callers_last_week: [],
      caller_changed: false,
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
      missed_last_week: false,
      callers_this_week: [{ called_by: 'Ada', called_by_id: 9, outcome: 'called', called_at: '' }],
      callers_last_week: [{ called_by: 'Ben', called_by_id: 8, outcome: 'called', called_at: '' }],
      caller_changed: true,
      hold: null,
    },
  ],
};

describe('CallBookPage', () => {
  beforeEach(() => {
    customersAPI.callBook.mockResolvedValue({ data: book });
    customersAPI.markCall.mockResolvedValue({ data: { called_this_week: true } });
    customersAPI.holdCall.mockResolvedValue({ data: { day_claim: true, hold_minutes: 480 } });
    customersAPI.callBookDayLog.mockResolvedValue({
      data: {
        day: '2026-11-16',
        count: 1,
        callers: ['Ada'],
        results: [{
          customer_id: 2,
          name: 'Called Shop',
          called_by: 'Ada',
          outcome: 'called',
          request_summary: 'Wants webbing',
          called_at: '2026-11-16T10:00:00+03:00',
        }],
      },
    });
    Object.assign(navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  test('searches customers by name the same way as the other lists', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    fireEvent.change(screen.getByTestId('call-book-search'), {
      target: { value: 'Javala' },
    });
    await waitFor(() => {
      expect(customersAPI.callBook).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'Javala' }),
      );
    });
  });

  test('shows the next customer and copies the number instead of dialling', async () => {
    render(<CallBookPage />);
    expect(await screen.findByText('Not Called Shop')).toBeInTheDocument();
    expect(screen.getByText('Monday · Starehe')).toBeInTheDocument();
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

  test('corrected: day plan ticker shows called vs not called for the selected day', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    expect(screen.getByTestId('call-day-ticker')).toBeInTheDocument();
    expect(screen.getByTestId('call-day-ticker-called')).toHaveTextContent('1 called');
    expect(screen.getByTestId('call-day-ticker-not-called')).toHaveTextContent('1 not called');
    expect(screen.getByTestId('call-workspace-day-ticker')).toHaveTextContent(
      '1 called · 1 not called · 2 on plan',
    );
    expect(screen.getByTestId('call-day-ticker').textContent).not.toMatch(/0718/);
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

  test('corrected: updates notes for a customer already recorded this week', async () => {
    const { toast } = require('../../utils/toast');
    customersAPI.markCall.mockResolvedValue({
      data: { called_this_week: true, updated: true, request_summary: 'Updated webbing note' },
    });
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('tab', { name: 'Weekly schedule' }));
    expect(await screen.findByText('Called Shop')).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole('button', { name: 'Update call notes for Called Shop' }),
    );
    expect(await screen.findByTestId('call-current-note')).toHaveTextContent('Wants webbing');
    expect(screen.getByRole('button', { name: 'Update notes' })).toBeInTheDocument();
    const notes = screen.getByLabelText('Notes for Called Shop');
    expect(notes).toHaveValue('Wants webbing');
    await userEvent.clear(notes);
    await userEvent.type(notes, 'Updated webbing note');
    await userEvent.click(screen.getByRole('button', { name: 'Update notes' }));
    await waitFor(() => {
      expect(customersAPI.markCall).toHaveBeenCalledWith(2, {
        outcome: 'called',
        request_summary: 'Updated webbing note',
        follow_up_on: '',
        follow_up_time: '',
      });
    });
    expect(toast.success).toHaveBeenCalledWith('Call notes updated.');
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

  test('corrected: save failure shows API detail not a generic toast', async () => {
    const { toast } = require('../../utils/toast');
    customersAPI.markCall.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Amina already called this customer today. Only one person can call them on this day.',
        },
      },
    });
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('button', { name: 'Save record' }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringMatching(/Amina already called this customer today/i),
      );
    });
    expect(toast.error).not.toHaveBeenCalledWith('Could not save this call.');
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
    await userEvent.click(screen.getByRole('button', { name: 'Open to record the call for Not Called Shop' }));
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
      status: 'all',
      page: 2,
      page_size: 10,
    }));
  });

  test('a customer someone else has is skipped and cannot be opened', async () => {
    customersAPI.callBook.mockResolvedValue({
      data: {
        ...book,
        results: [
          {
            ...book.results[0],
            hold: { held_by: 'Mercy', held_by_me: false, expires_at: '2026-11-24T10:00:00' },
          },
          {
            ...book.results[0],
            customer_id: 3,
            name: 'Free Shop',
            phone: '0718000003',
            previous_summary: '',
            hold: null,
          },
        ],
      },
    });
    render(<CallBookPage />);
    expect(await screen.findByRole('heading', { name: 'Free Shop' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Not Called Shop' })).not.toBeInTheDocument();
    expect(screen.queryByText('0718000001')).not.toBeInTheDocument();
    await waitFor(() => expect(customersAPI.holdCall).toHaveBeenCalledWith(3));
    expect(customersAPI.holdCall).not.toHaveBeenCalledWith(1);
    await userEvent.click(screen.getByRole('tab', { name: 'Weekly schedule' }));
    const blocked = screen.getByRole('button', {
      name: 'Mercy claimed this customer for today. Only one person can call them today.',
    });
    expect(blocked).toBeDisabled();
    expect(screen.getByText(/Mercy claimed this customer for today/)).toBeInTheDocument();
  });

  test('who called tab loads the day log without phones', async () => {
    render(<CallBookPage />);
    await screen.findByText('Not Called Shop');
    await userEvent.click(screen.getByRole('tab', { name: 'Who called' }));
    expect(await screen.findByTestId('call-day-log')).toBeInTheDocument();
    await waitFor(() => expect(customersAPI.callBookDayLog).toHaveBeenCalled());
    expect(screen.getByText('Called Shop')).toBeInTheDocument();
    expect(screen.getByText(/Callers that day: Ada/)).toBeInTheDocument();
    expect(screen.queryByText('0718000002')).not.toBeInTheDocument();
  });

  test('queue shows missed-last-week priority on the open customer', async () => {
    render(<CallBookPage />);
    expect(await screen.findByTestId('missed-last-week')).toHaveTextContent(/Not called last week/);
  });

  test('clicking a customer shows their general information', async () => {
    customersAPI.callBook.mockResolvedValue({
      data: {
        ...book,
        results: [{
          ...book.results[0],
          owner_name: 'Asha',
          contact_person: 'Kamau',
          address: 'Stall 4',
          customer_code: 'INFO-1',
          engagement_tier: 'buyer',
          buyer_segment: 'at_risk',
          typical_goods: ['Zippers'],
          last_purchased_at: '2026-11-01T10:00:00+03:00',
        }],
      },
    });
    render(<CallBookPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'View information for Not Called Shop' }));
    expect(await screen.findByRole('heading', { name: 'Customer information' })).toBeInTheDocument();
    const info = screen.getByTestId('call-customer-info');
    expect(info).toHaveTextContent('Asha');
    expect(info).toHaveTextContent('Kamau');
    expect(info).toHaveTextContent('Stall 4');
    expect(info).toHaveTextContent('Zippers');
    expect(info).toHaveTextContent('Cooling off');
    expect(info).toHaveTextContent('0718000001');
    expect(info).not.toHaveTextContent('0718999888');
  });
});
