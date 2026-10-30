import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import StickyNotesGate from './StickyNotesGate';
import { dailyNotesAPI } from '../../services/api';
import { getStoredAuth } from '../../utils/roleAccess';
import { toast } from '../../utils/toast';
import { resetLoginOverlayQueue } from '../../utils/loginOverlayQueue';
import {
  SALE_CORRECTION_SUBMITTED_EVENT,
} from '../../utils/saleCorrectionEvents';

const mockNavigate = jest.fn();
const mockLocation = { pathname: '/', search: '' };

jest.mock('../../services/api', () => ({
  dailyNotesAPI: {
    blocking: jest.fn(),
    toggleDone: jest.fn(),
  },
}));

jest.mock('../../utils/roleAccess', () => ({
  getStoredAuth: jest.fn(),
}));

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => mockLocation,
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), warning: jest.fn() },
}));

const returnedSaleNote = (id, saleId, titleSuffix = '') => ({
  id,
  title: `Approval rejected: sale completion${titleSuffix}`,
  content:
    `Bea returned sale S-${saleId}.\nTheir comment:\nWrong prices\n---\nsource: pending_change\nid: ${id}\nsale_id: ${saleId}\nref: reject/sale/${saleId}/`,
  is_sticky: true,
  is_done: false,
  note_date: '2026-09-24',
  author_name: 'Bea',
  assigned_to: 20,
});

async function expandNote(id) {
  fireEvent.click(await screen.findByTestId(`sticky-note-expand-${id}`));
  expect(await screen.findByTestId(`sticky-note-body-${id}`)).toBeInTheDocument();
}

describe('StickyNotesGate', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockLocation.pathname = '/';
    mockLocation.search = '';
    resetLoginOverlayQueue();
    getStoredAuth.mockReturnValue({ user: { id: 20 } });
  });

  test('renders nothing when there are no blocking notes', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({ data: [] });
    const { container } = render(<StickyNotesGate />);
    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  test('shows compact strips and expands to mark sticky notes done', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 5,
          title: 'Till variance',
          content: 'Explain the short before selling.',
          is_sticky: true,
          is_done: false,
          note_date: '2026-09-24',
          days_carried_over: 3,
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
    expect(screen.getByText(/Carried over 3 days/)).toBeInTheDocument();
    expect(screen.queryByText(/Explain the short/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('sticky-note-tick-5')).not.toBeInTheDocument();

    await expandNote(5);
    expect(screen.getByText(/Explain the short/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('sticky-note-tick-5'));
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('sticky-note-tick-confirm-5'));
    await waitFor(() => expect(dailyNotesAPI.toggleDone).toHaveBeenCalledWith(5));
    await waitFor(() => expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument());
  });

  test('expanding a note does not mark it done', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        {
          id: 5,
          title: 'Till variance',
          content: 'Explain the short before selling.',
          is_sticky: true,
          is_done: false,
          assigned_to: 20,
        },
      ],
    });
    render(<StickyNotesGate />);
    await expandNote(5);
    expect(screen.getByText(/Explain the short/)).toBeInTheDocument();
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('sticky-note-tick-5'));
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('sticky-note-tick-cancel-5'));
    expect(screen.getByTestId('sticky-note-tick-5')).toBeInTheDocument();
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
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
    await expandNote(9);
    fireEvent.click(screen.getByTestId('sticky-note-tick-9'));
    fireEvent.click(screen.getByTestId('sticky-note-tick-confirm-9'));
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
    expect(screen.queryByText(/fill the shelf/i)).not.toBeInTheDocument();

    await expandNote(11);
    expect(screen.getByText(/fill the shelf/i)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('sticky-notes-continue'));
    expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument();
  });

  test('opens a returned sale instead of ticking the note', async () => {
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [returnedSaleNote(8, 99)],
    });
    render(<StickyNotesGate />);
    expect(await screen.findByText(/Returned sale — open and send back/i)).toBeInTheDocument();
    expect(screen.queryByTestId('sticky-note-tick-8')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sticky-note-open-sale-8')).not.toBeInTheDocument();

    await expandNote(8);
    fireEvent.click(screen.getByTestId('sticky-note-open-sale-8'));
    expect(mockNavigate).toHaveBeenCalledWith('/pos/billing?sale=99');
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument()
    );
  });

  test('keeps blocking on Terminal until a returned sale is opened', async () => {
    mockLocation.pathname = '/pos/billing';
    mockLocation.search = '';
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [
        returnedSaleNote(8, 99),
        returnedSaleNote(9, 100),
      ],
    });
    render(<StickyNotesGate />);
    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.getByText(/2 returned sales — open and send back/i)).toBeInTheDocument();
  });

  test('hides the gate when Terminal opens with ?sale= so editing is unblocked', async () => {
    mockLocation.pathname = '/pos/billing';
    mockLocation.search = '?sale=99';
    dailyNotesAPI.blocking.mockResolvedValue({
      data: [returnedSaleNote(8, 99), returnedSaleNote(9, 100)],
    });
    render(<StickyNotesGate />);
    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalled());
    expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument();
  });

  test('after correction submit, re-blocks when more returned sales remain', async () => {
    dailyNotesAPI.blocking
      .mockResolvedValueOnce({
        data: [returnedSaleNote(8, 99), returnedSaleNote(9, 100)],
      })
      .mockResolvedValueOnce({
        data: [returnedSaleNote(9, 100)],
      });

    render(<StickyNotesGate />);
    expect(await screen.findByText(/2 returned sales/i)).toBeInTheDocument();

    await expandNote(8);
    fireEvent.click(screen.getByTestId('sticky-note-open-sale-8'));
    await waitFor(() =>
      expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument()
    );

    await act(async () => {
      window.dispatchEvent(new CustomEvent(SALE_CORRECTION_SUBMITTED_EVENT));
    });

    expect(await screen.findByTestId('sticky-notes-gate')).toBeInTheDocument();
    expect(screen.getByText(/Returned sale — open and send back/i)).toBeInTheDocument();
    expect(dailyNotesAPI.blocking).toHaveBeenCalledTimes(2);
  });

  test('after correction submit, allows the system when no returned sales remain', async () => {
    dailyNotesAPI.blocking
      .mockResolvedValueOnce({ data: [returnedSaleNote(8, 99)] })
      .mockResolvedValueOnce({ data: [] });

    render(<StickyNotesGate />);
    await expandNote(8);
    fireEvent.click(screen.getByTestId('sticky-note-open-sale-8'));
    await waitFor(() =>
      expect(screen.queryByTestId('sticky-notes-gate')).not.toBeInTheDocument()
    );

    await act(async () => {
      window.dispatchEvent(new CustomEvent(SALE_CORRECTION_SUBMITTED_EVENT));
    });

    await waitFor(() => expect(dailyNotesAPI.blocking).toHaveBeenCalledTimes(2));
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
    await expandNote(12);
    fireEvent.click(screen.getByTestId('sticky-note-tick-12'));
    expect(dailyNotesAPI.toggleDone).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('sticky-note-tick-confirm-12'));
    await waitFor(() => expect(dailyNotesAPI.toggleDone).toHaveBeenCalledWith(12));
  });
});
