import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DailyNoteForm from './DailyNoteForm';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  dailyNotesAPI: {
    create: jest.fn(),
    update: jest.fn(),
    staff: jest.fn(),
    roles: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

describe('DailyNoteForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    dailyNotesAPI.staff.mockResolvedValue({
      data: [{ id: 7, username: 'ann', display_name: 'Ann Cash' }],
    });
    dailyNotesAPI.roles.mockResolvedValue({
      data: [{ id: 3, name: 'Sales Personnel' }],
    });
    dailyNotesAPI.create.mockResolvedValue({ data: { id: 1 } });
    dailyNotesAPI.update.mockResolvedValue({ data: { id: 2 } });
  });

  test('saves a general note', async () => {
    const onSave = jest.fn();
    render(<DailyNoteForm defaultDate="2026-09-24" onClose={jest.fn()} onSave={onSave} />);
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Counted drawer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() =>
      expect(dailyNotesAPI.create).toHaveBeenCalledWith({
        note_date: '2026-09-24',
        title: '',
        content: 'Counted drawer',
        is_sticky: false,
      }),
    );
    expect(onSave).toHaveBeenCalled();
  });

  test('requires assignee for admin sticky notes', async () => {
    render(
      <DailyNoteForm
        defaultDate="2026-09-24"
        canAssignToOthers
        onClose={jest.fn()}
        onSave={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Fix till first' },
    });
    fireEvent.click(screen.getByTestId('note-is-sticky'));
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    expect(toast.warning).toHaveBeenCalled();
    expect(dailyNotesAPI.create).not.toHaveBeenCalled();
    fireEvent.change(await screen.findByTestId('note-assigned-to'), {
      target: { value: '7' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() =>
      expect(dailyNotesAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ is_sticky: true, assigned_to: 7 }),
      ),
    );
  });

  test('assigns a sticky note to a whole role', async () => {
    dailyNotesAPI.create.mockResolvedValue({ data: { id: 9, created_count: 2 } });
    render(
      <DailyNoteForm
        defaultDate="2026-09-24"
        canAssignToOthers
        onClose={jest.fn()}
        onSave={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Count before you sell' },
    });
    fireEvent.click(screen.getByTestId('note-is-sticky'));
    fireEvent.click(screen.getByTestId('note-assign-role'));
    fireEvent.change(await screen.findByTestId('note-assigned-role'), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() =>
      expect(dailyNotesAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ is_sticky: true, assigned_role: 3 }),
      ),
    );
    expect(toast.success).toHaveBeenCalledWith('Note sent to 2 people');
  });

  test('updates an existing note', async () => {
    render(
      <DailyNoteForm
        note={{
          id: 4,
          note_date: '2026-09-24',
          title: 'Old',
          content: 'Was',
          is_sticky: false,
        }}
        onClose={jest.fn()}
        onSave={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Updated' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Update$/i }));
    await waitFor(() => expect(dailyNotesAPI.update).toHaveBeenCalledWith(4, expect.any(Object)));
  });

  test('warns when content is empty', () => {
    render(<DailyNoteForm defaultDate="2026-09-24" onClose={jest.fn()} onSave={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    expect(toast.warning).toHaveBeenCalled();
  });

  test('warns on invalid date, save errors, and staff load failure', async () => {
    dailyNotesAPI.staff.mockRejectedValue(new Error('nope'));
    dailyNotesAPI.create.mockRejectedValue({ response: { data: { error: 'Nope' } } });
    render(
      <DailyNoteForm
        defaultDate="not-a-date"
        canAssignToOthers
        onClose={jest.fn()}
        onSave={jest.fn()}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Counted drawer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    expect(toast.warning).toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('note-date'), {
      target: { value: '2026-09-24' },
    });
    await waitFor(() => expect(dailyNotesAPI.staff).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Nope'));
  });

  test('self sticky note without assignee picker', async () => {
    render(<DailyNoteForm defaultDate="2026-09-24" onClose={jest.fn()} onSave={jest.fn()} />);
    fireEvent.change(screen.getByPlaceholderText(/What happened today/i), {
      target: { value: 'Block myself' },
    });
    fireEvent.click(screen.getByTestId('note-is-sticky'));
    expect(screen.getByText(/will block you/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));
    await waitFor(() =>
      expect(dailyNotesAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({ is_sticky: true }),
      ),
    );
  });
});
