import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
import {
  SALE_CORRECTION_SUBMITTED_EVENT,
} from '../../utils/saleCorrectionEvents';
import { cn } from '../../lib/cn';

/**
 * Blocking sticky inbox for returned sales and must-tick notes.
 *
 * Returned-sale flow:
 * 1. Open sale → gate hides so Terminal Rectify is editable
 * 2. Submit for approval → sticky for that sale clears on the server
 * 3. Gate reloads; if more returned sales remain, it blocks the app again
 */
export default function StickyNotesGate() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = getStoredAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [confirmTickId, setConfirmTickId] = useState(null);
  const [dismissedGeneral, setDismissedGeneral] = useState(false);
  const [expandedIds, setExpandedIds] = useState([]);
  /** True only while Terminal is open for a returned-sale fix. */
  const [suppressForFix, setSuppressForFix] = useState(false);
  /** Set once staff actually land on Terminal for a fix; leaving then re-blocks. */
  const reachedBillingFixRef = useRef(false);

  const loadBlocking = useCallback(async () => {
    setLoading(true);
    try {
      const res = await dailyNotesAPI.blocking();
      const rows = Array.isArray(res.data) ? res.data : [];
      setNotes(rows.filter((n) => !n.is_done));
      setDismissedGeneral(false);
      setExpandedIds([]);
      setConfirmTickId(null);
    } catch {
      setNotes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBlocking();
  }, [loadBlocking, user?.id]);

  // Suppress while fixing on Terminal; restore sticky gate only after leaving Terminal.
  useEffect(() => {
    const onBilling = String(location.pathname || '').startsWith('/pos/billing');
    const params = new URLSearchParams(location.search || '');
    const openingSale = Boolean(params.get('sale'));

    if (onBilling && (openingSale || suppressForFix)) {
      reachedBillingFixRef.current = true;
      if (openingSale) {
        setSuppressForFix(true);
      }
      return undefined;
    }

    if (reachedBillingFixRef.current && !onBilling) {
      reachedBillingFixRef.current = false;
      setSuppressForFix(false);
      loadBlocking();
    }
    return undefined;
  }, [location.pathname, location.search, suppressForFix, loadBlocking]);

  // After a correction is submitted, re-check. Remaining returned sales stay sticky.
  useEffect(() => {
    const onSubmitted = () => {
      reachedBillingFixRef.current = false;
      setSuppressForFix(false);
      loadBlocking();
    };
    window.addEventListener(SALE_CORRECTION_SUBMITTED_EVENT, onSubmitted);
    return () => window.removeEventListener(SALE_CORRECTION_SUBMITTED_EVENT, onSubmitted);
  }, [loadBlocking]);

  const handleToggle = async (note) => {
    if (noticeRequiresSaleFix(note) || !canToggleDailyNote(note, user?.id, true)) return;
    // Require an explicit confirm so expanding / reading a note never marks it done.
    if (confirmTickId !== note.id) {
      setConfirmTickId(note.id);
      return;
    }
    setTogglingId(note.id);
    try {
      const res = await dailyNotesAPI.toggleDone(note.id);
      setNotes((prev) => prev.map((n) => (n.id === note.id ? res.data : n)).filter((n) => !n.is_done));
      setExpandedIds((prev) => prev.filter((id) => id !== note.id));
      setConfirmTickId(null);
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
    setExpandedIds([]);
    setSuppressForFix(true);
    navigate(path);
  };

  const toggleExpanded = (noteId) => {
    setConfirmTickId((prev) => (prev === noteId ? null : prev));
    setExpandedIds((prev) =>
      prev.includes(noteId) ? prev.filter((id) => id !== noteId) : [...prev, noteId]
    );
  };

  const stickyBlocking = hasBlockingStickyNotes(notes);
  const returnedSaleOpen = notes.some((n) => noticeRequiresSaleFix(n));
  const returnedCount = notes.filter((n) => noticeRequiresSaleFix(n)).length;
  const showInbox = hasInboxNotes(notes) && (stickyBlocking || !dismissedGeneral);
  const gateOpen = Boolean(!loading && showInbox && !suppressForFix);

  useLayoutEffect(() => {
    setStickyNotesOverlay({ loading, open: gateOpen });
  }, [loading, gateOpen]);

  useEffect(() => () => setStickyNotesOverlay({ loading: false, open: false }), []);

  if (!gateOpen) {
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
                ? returnedCount > 1
                  ? `${returnedCount} returned sales — open and send back`
                  : 'Returned sale — open and send back'
                : 'Notes that must be ticked'
              : 'Notes for you'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {stickyBlocking
              ? returnedSaleOpen
                ? 'Open a sale to edit it. After you send it back, any remaining sales stay here until fixed.'
                : 'Tap a note to open it, then mark it done.'
              : 'Tap a note to read it. Mark done when finished, or continue.'}
          </p>
        </div>
        <ul className="min-h-0 flex-1 divide-y overflow-y-auto" data-testid="sticky-notes-gate-list">
          {notes.map((note) => {
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
                      ) : confirmTickId === note.id ? (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            disabled={togglingId === note.id}
                            data-testid={`sticky-note-tick-confirm-${note.id}`}
                            onClick={() => handleToggle(note)}
                          >
                            {togglingId === note.id ? 'Saving…' : 'Confirm done'}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={togglingId === note.id}
                            data-testid={`sticky-note-tick-cancel-${note.id}`}
                            onClick={() => setConfirmTickId(null)}
                          >
                            Cancel
                          </Button>
                        </>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          disabled={togglingId === note.id}
                          data-testid={`sticky-note-tick-${note.id}`}
                          onClick={() => handleToggle(note)}
                        >
                          Mark done
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
