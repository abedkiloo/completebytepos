import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import LeavePage from './LeavePage';

jest.mock('../../services/api', () => ({
  leaveAPI: {
    list: jest.fn(),
    create: jest.fn(),
    decide: jest.fn(),
    allowance: jest.fn(),
    saveAllowance: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const { leaveAPI } = require('../../services/api');

beforeEach(() => {
  localStorage.setItem('enabled_modules', JSON.stringify({
    employees: {
      is_enabled: true,
      features: { leave_requests: { is_enabled: true } },
    },
  }));
});

test('a staff request is sent and a manager can approve it', async () => {
  leaveAPI.list.mockResolvedValue({
    data: {
      results: [{
        id: 4,
        kind: 'sick',
        day: '2026-11-20',
        note: 'Fever',
        status: 'pending',
        requester_name: 'Asha',
        can_decide: true,
        decision_note: '',
        decided_by_name: '',
      }],
      allowance: { limit: 1, used: 0, remaining: 1, custom: false, month: '2026-11' },
      can_configure: true,
    },
  });
  leaveAPI.allowance.mockResolvedValue({
    data: { shop_days: 1, people: [{ id: 8, name: 'Asha', monthly_leave_days: null, effective: 1 }] },
  });
  leaveAPI.saveAllowance.mockResolvedValue({ data: { shop_days: 2 } });
  leaveAPI.create.mockResolvedValue({ data: { id: 5 } });
  leaveAPI.decide.mockResolvedValue({ data: { status: 'approved' } });

  render(<LeavePage />);
  expect(await screen.findByTestId('leave-allowance')).toHaveTextContent('1 of 1 day off left in 2026-11');
  fireEvent.change(screen.getByLabelText('Days off each month for everyone'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save for everyone' }));
  await waitFor(() => expect(leaveAPI.saveAllowance).toHaveBeenCalledWith({ monthly_leave_days: 2 }));
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
  await waitFor(() => expect(leaveAPI.decide).toHaveBeenCalledWith(4, { decision: 'approved' }));

  fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'leave' } });
  fireEvent.change(screen.getByLabelText('Day'), { target: { value: '2026-11-21' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send request' }));
  await waitFor(() => expect(leaveAPI.create).toHaveBeenCalledWith({
    kind: 'leave',
    day: '2026-11-21',
    note: '',
  }));
});
