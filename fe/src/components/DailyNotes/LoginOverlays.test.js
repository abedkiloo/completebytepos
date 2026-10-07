import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import PendingTasksOnLogin from './PendingTasksOnLogin';
import StickyNotesGate from './StickyNotesGate';
import { dailyNotesAPI, dailyTasksAPI } from '../../services/api';
import { getStoredAuth } from '../../utils/roleAccess';
import { fetchNavBadgeCounts } from '../../utils/navBadges';
import { resetLoginOverlayQueue } from '../../utils/loginOverlayQueue';
import { clearPendingTasksPromptDismissed } from '../../utils/dailyNotesTaskAccess';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  MemoryRouter: ({ children }) => <>{children}</>,
  useNavigate: () => mockNavigate,
}));

jest.mock('../../services/api', () => ({
  dailyNotesAPI: {
    blocking: jest.fn(),
    toggleDone: jest.fn(),
  },
  dailyTasksAPI: {
    pending: jest.fn(),
    toggleDone: jest.fn(),
  },
}));

jest.mock('../../utils/navBadges', () => ({
  fetchNavBadgeCounts: jest.fn(),
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
  userMayEditFinancialFieldsFromStorage: () => false,
}));

jest.mock('../../utils/navAccess', () => ({
  getPersonaFromStorage: () => 'sales',
}));

jest.mock('../../utils/dailyNotesAccess', () => ({
  userMayOpenDailyNotes: () => true,
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: {}, loading: false }),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), warning: jest.fn(), success: jest.fn() },
}));

function renderLoginOverlays() {
  return render(
    <>
      <StickyNotesGate />
      <PendingTasksOnLogin />
    </>
  );
}

const returnedSaleNote = {
  id: 8,
  title: 'Approval rejected: sale completion',
  content:
    'admin returned sale SALE-AF1757BF for walk-in customer.\nTheir comment:\nUpdate sales\n---\nsource: pending_change\nid: 6\nsale_id: 37\nref: reject/sale/37/',
  is_sticky: true,
  is_done: false,
  note_date: '2026-09-28',
  author_name: 'admin',
  assigned_to: 20,
};

const pendingTask = {
  id: 3,
  title: 'Count till',
  is_done: false,
  task_date: '2026-09-28',
  days_carried_over: 4,
  assigned_to: 20,
};

describe('login overlays', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetLoginOverlayQueue();
    clearPendingTasksPromptDismissed();
    getStoredAuth.mockReturnValue({ user: { id: 20 }, permissions: [] });
    fetchNavBadgeCounts.mockResolvedValue({ pendingTasks: 1, pendingApprovals: 0 });
    dailyTasksAPI.pending.mockResolvedValue({ data: [pendingTask] });
  });

  test('shows the returned-sale gate first and the welcome summary after it is done', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({ data: [returnedSaleNote] });

    renderLoginOverlays();

    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.queryByTestId('pending-tasks-on-login')).not.toBeInTheDocument();
    expect(screen.queryByText(/Welcome back/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('sticky-note-expand-8'));
    fireEvent.click(await screen.findByTestId('sticky-note-open-sale-8'));
    expect(mockNavigate).toHaveBeenCalledWith('/pos/billing?sale=37');

    expect(await screen.findByTestId('pending-tasks-on-login')).toBeInTheDocument();
    expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument();
    expect(screen.getByText(/Welcome back/i)).toBeInTheDocument();
    expect(screen.getByText(/Carried over 4 days/)).toBeInTheDocument();
  });

  test('shows the welcome summary after a dismissible note is continued', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 11,
          title: 'Restock sugar',
          content: 'Please fill the shelf.',
          is_sticky: false,
          is_done: false,
          assigned_to: 20,
        },
      ],
    });

    renderLoginOverlays();

    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.queryByTestId('pending-tasks-on-login')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('sticky-notes-continue'));

    expect(await screen.findByTestId('pending-tasks-on-login')).toBeInTheDocument();
    expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument();
  });
});
