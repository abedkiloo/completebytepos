import React, { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Loader2, NotebookPen } from 'lucide-react';

import { Button } from '../ui/button';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth } from '../../utils/roleAccess';
import {
  canToggleDailyNote,
  hasBlockingStickyNotes,
  hasInboxNotes,
  isStickyNote,
  noteKindLabel,
} from '../../utils/dailyNotesSticky';
import {
  noticeRequiresSaleFix,
  parseApprovalRejectionNotice,
  rejectedSaleFixPath,
} from '../../utils/approvalReturn';
import { formatDisplayDate, carriedOverLabel } from '../../utils/dailyNotesTasks';
import { setStickyNotesOverlay } from '../../utils/loginOverlayQueue';

/**
 * On login, show notes assigned to the current user.
 * Must-tick notes must be ticked before the rest of the app can be used.
 * Returned-sale notes cannot be ticked — staff open the sale and send it back.
 */
export default function StickyNotesGate() {
  const navigate = useNavigate();
  const { user } = getStoredAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [dismissedGeneral, setDismissedGeneral] = useState(false);
  const [releasedIds, setReleasedIds] = useState([]);

  const loadBlocking = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dailyNotesAPI.blocking();
      const rows = Array.isArray(res.data) ? res.data : [];
      setNotes(rows.filter((n) => !n.is_done));
      setDismissedGeneral(false);
      setReleasedIds([]);
    } catch {
      setNotes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBlocking();
  }, [loadBlocking, user?.id]);

  const handleToggle = async (note) => {
    if (noticeRequiresSaleFix(note) || !canToggleDailyNote(note, user?.id, true)) return;
    setTogglingId(note.id);
    try {
      const res = await dailyNotesAPI.toggleDone(note.id);
      setNotes((prev) => prev.map((n) => (n.id === note.id ? res.data : n)).filter((n) => !n.is_done));
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not tick this note');
    } finally {
      setTogglingId(null);
    }
  };

  const handleOpenSale = (note) => {
    const path = rejectedSaleFixPath(
      parseApprovalRejectionNotice(note.content),
      note.title
    );
    if (!path) {
      toast.warning('Open POS to update this sale.');
      return;
    }
    setReleasedIds((prev) => (prev.includes(note.id) ? prev : [...prev, note.id]));
    navigate(path);
  };

  const visibleNotes = notes.filter((n) => !releasedIds.includes(n.id));
  const stickyBlocking = hasBlockingStickyNotes(visibleNotes);
  const returnedSaleOpen = visibleNotes.some((n) => noticeRequiresSaleFix(n));
  const showInbox = hasInboxNotes(visibleNotes) && (stickyBlocking || !dismissedGeneral);

  useLayoutEffect(() => {
    setStickyNotesOverlay({ loading, open: Boolean(!loading && showInbox) });
  }, [loading, showInbox]);

  useEffect(() => () => setStickyNotesOverlay({ loading: false, open: false }), []);

  if (loading || !showInbox) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[3200] flex items-center justify-center overflow-y-auto bg-black/70 p-4"
      data-testid="sticky-notes-gate"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="sticky-notes-gate-title"
    >
      <div className="my-auto flex max-h-[90dvh] w-full max-w-md flex-col overflow-hidden rounded-lg border bg-background shadow-xl">
        <div className="shrink-0 border-b px-4 py-3">
          <h2 id="sticky-notes-gate-title" className="flex items-center gap-2 text-base font-semibold">
            {stickyBlocking ? (
              <AlertTriangle className="h-4 w-4 text-destructive" />
            ) : (
              <NotebookPen className="h-4 w-4" />
            )}
            {stickyBlocking
              ? returnedSaleOpen
                ? 'Returned sale — open and send back'
                : 'Notes that must be ticked'
              : 'Notes for you'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {stickyBlocking
              ? returnedSaleOpen
                ? 'The manager left a comment. Open that sale, update it, then send it back for approval. Ticking this note is not enough.'
                : 'Tick each must-tick note below before you continue. You cannot use the rest of the system until these are sorted.'
              : 'These notes were assigned to you. Read them, tick them if you are done, or continue.'}
          </p>
        </div>
        <ul className="min-h-0 flex-1 divide-y overflow-y-auto" data-testid="sticky-notes-gate-list">
          {visibleNotes.map((note) => {
            const saleFix = noticeRequiresSaleFix(note);
            return (
              <li key={note.id} className="flex items-start gap-3 px-4 py-3">
                {saleFix ? null : (
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0"
                    checked={Boolean(note.is_done)}
                    disabled={togglingId === note.id}
                    onChange={() => handleToggle(note)}
                    aria-label={`Tick note ${note.title || note.id}`}
                    data-testid={`sticky-note-tick-${note.id}`}
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {note.title || noteKindLabel(note)}
                  </p>
                  <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-muted-foreground">
                    {note.content}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatDisplayDate(note.note_date)}
                    {note.author_name ? ` · from ${note.author_name}` : ''}
                    {saleFix ? ' · Fix sale' : isStickyNote(note) ? ' · Must tick' : ''}
                    {carriedOverLabel(note) ? ` · ${carriedOverLabel(note)}` : ''}
                  </p>
                  {saleFix ? (
                    <Button
                      type="button"
                      size="sm"
                      className="mt-2"
                      data-testid={`sticky-note-open-sale-${note.id}`}
                      onClick={() => handleOpenSale(note)}
                    >
                      Open sale
                    </Button>
                  ) : null}
                </div>
                {togglingId === note.id ? (
                  <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                ) : null}
              </li>
            );
          })}
        </ul>
        <div className="flex shrink-0 flex-col gap-2 border-t px-4 py-3">
          <Button type="button" variant="outline" className="w-full" onClick={loadBlocking}>
            Refresh
          </Button>
          {!stickyBlocking ? (
            <Button
              type="button"
              className="w-full"
              data-testid="sticky-notes-continue"
              onClick={() => setDismissedGeneral(true)}
            >
              Continue
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
