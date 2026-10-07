import React, { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ChevronDown, Loader2, NotebookPen } from 'lucide-react';

import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
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
import { cn } from '../../lib/cn';

/**
 * On login, show notes assigned to the current user as compact expandable strips.
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
  const [expandedIds, setExpandedIds] = useState([]);

  const loadBlocking = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dailyNotesAPI.blocking();
      const rows = Array.isArray(res.data) ? res.data : [];
      setNotes(rows.filter((n) => !n.is_done));
      setDismissedGeneral(false);
      setReleasedIds([]);
      setExpandedIds([]);
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
      setExpandedIds((prev) => prev.filter((id) => id !== note.id));
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

  const toggleExpanded = (noteId) => {
    setExpandedIds((prev) =>
      prev.includes(noteId) ? prev.filter((id) => id !== noteId) : [...prev, noteId]
    );
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
                ? 'Open each sale below, fix it, then send it back.'
                : 'Tap a note to open it, then mark it done.'
              : 'Tap a note to read it. Mark done when finished, or continue.'}
          </p>
        </div>
        <ul className="min-h-0 flex-1 divide-y overflow-y-auto" data-testid="sticky-notes-gate-list">
          {visibleNotes.map((note) => {
            const saleFix = noticeRequiresSaleFix(note);
            const expanded = expandedIds.includes(note.id);
            const title = note.title || noteKindLabel(note);
            const carried = carriedOverLabel(note);
            return (
              <li key={note.id} className="px-3 py-2" data-testid={`sticky-note-strip-${note.id}`}>
                <div className="flex items-start gap-2">
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-start gap-2 rounded-md px-1 py-1 text-left hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onClick={() => toggleExpanded(note.id)}
                    aria-expanded={expanded}
                    data-testid={`sticky-note-expand-${note.id}`}
                  >
                    <ChevronDown
                      className={cn(
                        'mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
                        expanded ? 'rotate-0' : '-rotate-90',
                      )}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium leading-snug">{title}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        {saleFix ? (
                          <Badge variant="destructive" className="text-[10px]">
                            Fix sale
                          </Badge>
                        ) : isStickyNote(note) ? (
                          <Badge variant="destructive" className="text-[10px]">
                            Must tick
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-[10px]">
                            Note
                          </Badge>
                        )}
                        {note.author_name ? (
                          <span className="text-[11px] text-muted-foreground">
                            from {note.author_name}
                          </span>
                        ) : null}
                        {carried ? (
                          <span className="text-[11px] text-muted-foreground">{carried}</span>
                        ) : null}
                      </div>
                    </div>
                  </button>
                  {togglingId === note.id ? (
                    <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                  ) : null}
                </div>

                {expanded ? (
                  <div
                    className="mt-2 space-y-2 rounded-md border bg-muted/20 px-3 py-2"
                    data-testid={`sticky-note-body-${note.id}`}
                  >
                    <p className="whitespace-pre-wrap break-words text-sm text-muted-foreground">
                      {note.content || 'No details on this note.'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDisplayDate(note.note_date)}
                      {note.author_name ? ` · from ${note.author_name}` : ''}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      {saleFix ? (
                        <Button
                          type="button"
                          size="sm"
                          data-testid={`sticky-note-open-sale-${note.id}`}
                          onClick={() => handleOpenSale(note)}
                        >
                          Open sale
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          disabled={togglingId === note.id}
                          data-testid={`sticky-note-tick-${note.id}`}
                          onClick={() => handleToggle(note)}
                        >
                          {togglingId === note.id ? 'Saving…' : 'Mark done'}
                        </Button>
                      )}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => toggleExpanded(note.id)}
                      >
                        Collapse
                      </Button>
                    </div>
                  </div>
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
