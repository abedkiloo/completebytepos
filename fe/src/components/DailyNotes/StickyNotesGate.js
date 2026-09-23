import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

import { Button } from '../ui/button';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth } from '../../utils/roleAccess';
import { canToggleDailyNote, hasBlockingStickyNotes } from '../../utils/dailyNotesSticky';
import { formatDisplayDate } from '../../utils/dailyNotesTasks';

/**
 * Blocks the rest of the app until the current user's sticky notes are ticked.
 */
export default function StickyNotesGate() {
  const { user } = getStoredAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);

  const loadBlocking = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dailyNotesAPI.blocking();
      const rows = Array.isArray(res.data) ? res.data : [];
      setNotes(rows);
    } catch {
      setNotes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBlocking();
  }, [loadBlocking]);

  const handleToggle = async (note) => {
    if (!canToggleDailyNote(note, user?.id, true)) return;
    setTogglingId(note.id);
    try {
      const res = await dailyNotesAPI.toggleDone(note.id);
      setNotes((prev) => prev.map((n) => (n.id === note.id ? res.data : n)).filter((n) => !n.is_done));
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not tick this sticky note');
    } finally {
      setTogglingId(null);
    }
  };

  if (loading || !hasBlockingStickyNotes(notes)) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[3200] flex items-center justify-center bg-black/70 p-4"
      data-testid="sticky-notes-gate"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="sticky-notes-gate-title"
    >
      <div className="w-full max-w-md rounded-lg border bg-background shadow-xl">
        <div className="border-b px-4 py-3">
          <h2 id="sticky-notes-gate-title" className="flex items-center gap-2 text-base font-semibold">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            Sticky notes need attention
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Tick each sticky note below before you continue. You cannot use the rest of the system
            until these are sorted.
          </p>
        </div>
        <ul className="max-h-[50dvh] divide-y overflow-y-auto">
          {notes.map((note) => (
            <li key={note.id} className="flex items-start gap-3 px-4 py-3">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0"
                checked={Boolean(note.is_done)}
                disabled={togglingId === note.id}
                onChange={() => handleToggle(note)}
                aria-label={`Tick sticky note ${note.title || note.id}`}
                data-testid={`sticky-note-tick-${note.id}`}
              />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{note.title || 'Sticky note'}</p>
                <p className="mt-0.5 whitespace-pre-wrap text-sm text-muted-foreground">
                  {note.content}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDisplayDate(note.note_date)}
                  {note.author_name ? ` · from ${note.author_name}` : ''}
                </p>
              </div>
              {togglingId === note.id ? (
                <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
              ) : null}
            </li>
          ))}
        </ul>
        <div className="border-t px-4 py-3">
          <Button type="button" variant="outline" className="w-full" onClick={loadBlocking}>
            Refresh
          </Button>
        </div>
      </div>
    </div>
  );
}
