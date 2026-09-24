import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import StickyNotesGate from './StickyNotesGate';
import { dailyNotesAPI } from '../../services/api';
import { getStoredAuth } from '../../utils/roleAccess';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  dailyNotesAPI: {
    blocking: jest.fn(),
    toggleDone: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn() },
}));

describe('StickyNotesGate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getStoredAuth.mockReturnValue({ user: { id: 20 } });
  });

  test('renders nothing when there are no blocking notes', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({ data: [] });
    const { container } = render(<StickyNotesGate />);
    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  test('blocks until sticky notes are ticked', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 5,
          title: 'Till variance',
          content: 'Explain the short before selling.',
          is_sticky: true,
          is_done: false,
          note_date: '2026-09-24',
          author_name: 'Bea',
          assigned_to: 20,
        },
      ],
    });
    dailyNotesAPI.toggleDone.mockResolvedValue({
      data: { id: 5, is_sticky: true, is_done: true },
    });
    render(<StickyNotesGate />);
    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.getByText('Till variance')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('sticky-note-tick-5'));
    await waitFor(() => expect(dailyNotesAPI.toggleDone).toHaveBeenCalledWith(5));
    await waitFor(() => expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument());
  });

  test('hides after load failure and generic tick error', async () => {
    dailyNotesAPI.blocking.mockRejectedValueOnce(new Error('down'));
    const { container } = render(<StickyNotesGate />);
    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  test('generic tick error fallback', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [{ id: 9, content: 'Stop', is_sticky: true, is_done: false, assigned_to: 20 }],
    });
    dailyNotesAPI.toggleDone.mockRejectedValue({});
    render(<StickyNotesGate />);
    fireEvent.click(await screen.findByTestId('sticky-note-tick-9'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not tick this note'));
    fireEvent.click(screen.getByRole('button', { name: /Refresh/i }));
    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalledTimes(2));
  });

  test('shows assigned general notes on login and allows continue', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 11,
          title: 'Restock sugar',
          content: 'Please fill the shelf before opening.\nThanks.',
          is_sticky: false,
          is_done: false,
          note_date: '2026-09-24',
          author_name: 'Bea',
          assigned_to: 20,
        },
      ],
    });
    render(<StickyNotesGate />);
    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.getByText('Restock sugar')).toBeInTheDocument();
    expect(screen.getByText(/fill the shelf/i)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('sticky-notes-continue'));
    expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument();
  });

  test('ticks an assigned general note from the login inbox', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 12,
          content: 'Please restock',
          is_sticky: false,
          is_done: false,
          assigned_to: 20,
        },
      ],
    });
    dailyNotesAPI.toggleDone.mockResolvedValue({
      data: { id: 12, is_sticky: false, is_done: true },
    });
    render(<StickyNotesGate />);
    fireEvent.click(await screen.findByTestId('sticky-note-tick-12'));
    await waitFor(() => expect(dailyNotesAPI.toggleDone).toHaveBeenCalledWith(12));
  });
});
