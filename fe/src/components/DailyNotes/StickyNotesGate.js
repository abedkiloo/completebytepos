import React, { useCallback, useEffect, useState } from 'react';
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
import { formatDisplayDate } from '../../utils/dailyNotesTasks';

/**
 * On login, show notes assigned to the current user.
 * Must-tick notes must be ticked before the rest of the app can be used.
 */
export default function StickyNotesGate() {
  const { user } = getStoredAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [dismissedGeneral, setDismissedGeneral] = useState(false);

  const loadBlocking = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dailyNotesAPI.blocking();
      const rows = Array.isArray(res.data) ? res.data : [];
      setNotes(rows.filter((n) => !n.is_done));
      setDismissedGeneral(false);
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
    if (!canToggleDailyNote(note, user?.id, true)) return;
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

  const stickyBlocking = hasBlockingStickyNotes(notes);
  const showInbox = hasInboxNotes(notes) && (stickyBlocking || !dismissedGeneral);

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
            {stickyBlocking ? 'Notes that must be ticked' : 'Notes for you'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {stickyBlocking
              ? 'Tick each must-tick note below before you continue. You cannot use the rest of the system until these are sorted.'
              : 'These notes were assigned to you. Read them, tick them if you are done, or continue.'}
          </p>
        </div>
        <ul className="min-h-0 flex-1 divide-y overflow-y-auto" data-testid="sticky-notes-gate-list">
          {notes.map((note) => (
            <li key={note.id} className="flex items-start gap-3 px-4 py-3">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0"
                checked={Boolean(note.is_done)}
                disabled={togglingId === note.id}
                onChange={() => handleToggle(note)}
                aria-label={`Tick note ${note.title || note.id}`}
                data-testid={`sticky-note-tick-${note.id}`}
              />
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
                  {isStickyNote(note) ? ' · Must tick' : ''}
                </p>
              </div>
              {togglingId === note.id ? (
                <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
              ) : null}
            </li>
          ))}
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
