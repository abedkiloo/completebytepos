import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DailyNotes from './DailyNotes';
import { dailyNotesAPI, dailyTasksAPI, expensesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

const mockSearchParams = new URLSearchParams();

jest.mock('react-router-dom', () => ({
  useSearchParams: () => [mockSearchParams, jest.fn()],
}));

jest.mock('../../services/api', () => ({
  dailyNotesAPI: {
    list: jest.fn(),
    recentDates: jest.fn(),
    toggleDone: jest.fn(),
    delete: jest.fn(),
    staff: jest.fn(),
    roles: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    patch: jest.fn(),
  },
  dailyTasksAPI: {
    list: jest.fn(),
    toggleDone: jest.fn(),
    delete: jest.fn(),
  },
  expensesAPI: { resubmit: jest.fn() },
  incomeAPI: { resubmit: jest.fn() },
  pendingChangesAPI: { resubmit: jest.fn() },
  transfersAPI: { resubmit: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

jest.mock('../../utils/roleAccess', () => ({
  getPersonaFromStorage: () => 'manager',
  getStoredAuth: () => ({ user: { id: 20 } }),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: { allow_manager_view_all: true } }),
}));

jest.mock('../../utils/dailyNotesAccess', () => ({
  userMayViewAllDailyNotes: () => true,
}));

jest.mock('../../utils/navBadges', () => ({
  dispatchNavBadgesRefresh: jest.fn(),
}));

jest.mock('./DailyNoteForm', () => ({
  __esModule: true,
  default: ({ defaultAssignMode, note }) => (
    <div data-testid="daily-note-form-stub">
      {note ? 'edit' : defaultAssignMode || 'person'}
    </div>
  ),
}));

jest.mock('./DailyTaskForm', () => ({
  __esModule: true,
  default: () => <div data-testid="daily-task-form-stub" />,
}));

const longContent = `${'Please count the till before selling. '.repeat(12)}Thanks.`;

describe('DailyNotes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    dailyNotesAPI.recentDates.mockResolvedValue({ data: { dates: ['2026-09-24'] } });
    dailyNotesAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 5,
            note_date: '2026-09-24',
            title: 'Till',
            content: longContent,
            is_sticky: true,
            is_done: false,
            author: 9,
            author_name: 'Bea',
            assigned_to: 20,
            assigned_to_name: 'Ann',
            updated_at: '2026-09-24T08:00:00Z',
          },
          {
            id: 6,
            note_date: '2026-09-24',
            title: 'Mine',
            content: 'Short log',
            is_sticky: false,
            is_done: false,
            author: 20,
            author_name: 'Ann',
            assigned_to: 20,
            updated_at: '2026-09-24T09:00:00Z',
          },
          {
            id: 7,
            note_date: '2026-09-24',
            title: 'Approval rejected',
            content: 'source: expense\nid: 44\nFix the receipt.',
            is_sticky: false,
            is_done: false,
            author: 20,
            updated_at: '2026-09-24T09:30:00Z',
          },
        ],
      },
    });
    dailyTasksAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 3,
            title: 'Restock',
            description: 'Sugar',
            is_done: false,
            assigned_to: 20,
            assigned_to_name: 'Ann',
            author_id: 9,
            author_name: 'Bea',
          },
        ],
      },
    });
    dailyNotesAPI.toggleDone.mockResolvedValue({
      data: { id: 5, is_sticky: true, is_done: true, content: longContent, author: 9 },
    });
  });

  test('lists notes, completes them, and keeps long content scrollable', async () => {
    render(<DailyNotes />);
    expect(await screen.findByText('Till')).toBeInTheDocument();
    const content = screen.getByTestId('daily-note-content-5');
    expect(content.className).toMatch(/overflow-y-auto/);
    expect(content.className).toMatch(/max-h-32/);
    fireEvent.click(screen.getByLabelText(/Tick note Till/i));
    await waitFor(() => expect(dailyNotesAPI.toggleDone).toHaveBeenCalledWith(5));
  });

  test('opens a note-for-everyone form', async () => {
    render(<DailyNotes />);
    fireEvent.click(await screen.findByTestId('daily-note-everyone'));
    expect(await screen.findByTestId('daily-note-form-stub')).toHaveTextContent('everyone');
  });

  test('author can open edit for their own note', async () => {
    render(<DailyNotes />);
    expect(await screen.findByText('Mine')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('daily-note-edit-6'));
    expect(await screen.findByTestId('daily-note-form-stub')).toHaveTextContent('edit');
    fireEvent.click(screen.getByTestId('daily-note-delete-6'));
  });

  test('moves a note onto Doing', async () => {
    dailyNotesAPI.patch.mockResolvedValue({
      data: {
        id: 5,
        title: 'Till',
        content: longContent,
        is_sticky: true,
        is_done: false,
        in_progress: true,
        board_column: 'doing',
        author: 9,
      },
    });
    render(<DailyNotes />);
    expect(await screen.findByTestId('daily-notes-board')).toBeInTheDocument();
    expect(screen.getByTestId('daily-notes-column-todo')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('daily-note-move-5-doing'));
    await waitFor(() =>
      expect(dailyNotesAPI.patch).toHaveBeenCalledWith(5, { board_column: 'doing' }),
    );
  });

  test('toasts when a note cannot be moved', async () => {
    dailyNotesAPI.patch.mockRejectedValue({
      response: { data: { error: 'Nope' } },
    });
    render(<DailyNotes />);
    fireEvent.click(await screen.findByTestId('daily-note-move-5-doing'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Nope'));
  });

  test('resubmits an approval rejection from a note card', async () => {
    expensesAPI.resubmit.mockResolvedValue({});
    render(<DailyNotes />);
    fireEvent.click(await screen.findByRole('button', { name: /Send back for approval/i }));
    await waitFor(() => expect(expensesAPI.resubmit).toHaveBeenCalledWith(44));
  });

  test('shows empty day actions when nothing is logged', async () => {
    dailyNotesAPI.list.mockResolvedValue({ data: { results: [] } });
    dailyTasksAPI.list.mockResolvedValue({ data: { results: [] } });
    render(<DailyNotes />);
    expect(await screen.findByText(/Nothing for this day yet/i)).toBeInTheDocument();
  });

  test('toasts when the day fails to load', async () => {
    dailyNotesAPI.list.mockRejectedValue(new Error('down'));
    render(<DailyNotes />);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not load this day'));
  });
});
