import React, { useState } from 'react';
import { ChevronDown, Pencil, Redo2, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  NOTE_BOARD_COLUMNS,
  canToggleDailyNote,
  isStickyNote,
  noteKindLabel,
  notesForBoardColumn,
} from '../../utils/dailyNotesSticky';
import {
  canResubmitRejection,
  isApprovalRejectionNote,
  noticeRequiresSaleFix,
  parseApprovalRejectionNotice,
  rejectedSaleFixPath,
} from '../../utils/approvalReturn';
import { carriedOverLabel } from '../../utils/dailyNotesTasks';
import { priorityMeta } from '../../utils/dailyNotesPriority';
import { cn } from '../../lib/cn';
import PriorityBadge from './PriorityBadge';
import { isModuleFeatureEnabled } from '../../utils/moduleFeatures';
import { resolveMediaUrl } from '../../utils/mediaUrl';

export default function DailyNotesBoard({
  notes,
  viewAll,
  currentUserId,
  togglingNoteId,
  togglingChecklistKey,
  resubmittingKey,
  onToggle,
  onToggleChecklistItem,
  onMove,
  onEdit,
  onDelete,
  onResubmit,
  onFixSale,
  canModifyEntry,
  reviewers = [],
  onRequestReview,
  onCompleteReview,
}) {
  const [expandedIds, setExpandedIds] = useState([]);

  const toggleExpanded = (noteId) => {
    setExpandedIds((prev) =>
      prev.includes(noteId) ? prev.filter((id) => id !== noteId) : [...prev, noteId]
    );
  };

  return (
    <div
      className="grid grid-cols-1 gap-3 md:grid-cols-3"
      data-testid="daily-notes-board"
    >
      {NOTE_BOARD_COLUMNS.map((column) => {
        const cards = notesForBoardColumn(notes, column.id);
        return (
          <section
            key={column.id}
            className="flex min-h-[14rem] flex-col rounded-xl bg-muted/50 p-2"
            data-testid={`daily-notes-column-${column.id}`}
          >
            <header className="mb-2 flex items-center justify-between px-1 py-1">
              <h3 className="text-sm font-semibold tracking-wide text-foreground">
                {column.title}
              </h3>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground">
                {cards.length}
              </span>
            </header>
            <ul className="flex min-h-0 flex-1 flex-col gap-2">
              {cards.length === 0 ? (
                <li className="rounded-lg border border-dashed border-border/80 px-3 py-6 text-center text-xs text-muted-foreground">
                  No notes here
                </li>
              ) : (
                cards.map((note) => {
                  const expanded = expandedIds.includes(note.id);
                  const carried = carriedOverLabel(note);
                  const showPriority = isModuleFeatureEnabled(
                    'daily_notes',
                    'note_priority',
                    true,
                  );
                  const prio = priorityMeta(note.priority);
                  return (
                    <li
                      key={note.id}
                      className="overflow-hidden rounded-lg border bg-background shadow-sm"
                      data-testid={`daily-note-strip-${note.id}`}
                    >
                      {showPriority ? (
                        <div className={cn('h-1 w-full', prio.barClassName)} aria-hidden />
                      ) : null}
                      <button
                        type="button"
                        className="flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => toggleExpanded(note.id)}
                        aria-expanded={expanded}
                        data-testid={`daily-note-expand-${note.id}`}
                      >
                        <ChevronDown
                          className={cn(
                            'mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
                            expanded ? 'rotate-0' : '-rotate-90',
                          )}
                          aria-hidden
                        />
                        <div className="min-w-0 flex-1">
                          <p
                            className={cn(
                              'truncate text-sm font-semibold',
                              note.is_done && 'text-muted-foreground line-through',
                            )}
                          >
                            {note.title || 'Untitled note'}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-1">
                            {showPriority ? (
                              <PriorityBadge priority={note.priority} />
                            ) : null}
                            <Badge variant={isStickyNote(note) ? 'destructive' : 'secondary'}>
                              {noteKindLabel(note)}
                            </Badge>
                            {viewAll &&
                            (note.author_name ||
                              note.assigned_to_name ||
                              note.assigned_role_name) ? (
                              <span className="text-xs text-muted-foreground">
                                {note.assigned_to_name || note.assigned_role_name
                                  ? `For ${note.assigned_to_name || note.assigned_role_name}`
                                  : note.author_name}
                              </span>
                            ) : null}
                            {carried ? (
                              <Badge
                                variant="outline"
                                data-testid={`note-carried-over-${note.id}`}
                              >
                                {carried}
                              </Badge>
                            ) : null}
                            {Array.isArray(note.reviews) &&
                            note.reviews.some((row) => row.status === 'pending') ? (
                              <Badge
                                variant="outline"
                                data-testid={`note-review-waiting-${note.id}`}
                              >
                                Needs review
                              </Badge>
                            ) : null}
                            {Array.isArray(note.reviews) &&
                            note.reviews.length > 0 &&
                            note.reviews.every((row) => row.status === 'reviewed') ? (
                              <Badge
                                variant="outline"
                                data-testid={`note-review-done-${note.id}`}
                              >
                                Reviewed
                              </Badge>
                            ) : null}
                            {Array.isArray(note.checklist_items) &&
                            note.checklist_items.length > 0 ? (
                              <Badge
                                variant="outline"
                                data-testid={`note-checklist-count-${note.id}`}
                              >
                                {
                                  note.checklist_items.filter((item) => item.is_done)
                                    .length
                                }
                                /{note.checklist_items.length} checks
                              </Badge>
                            ) : null}
                          </div>
                        </div>
                      </button>

                      {expanded ? (
                        <div className="space-y-2 border-t px-3 py-2.5">
                          <p
                            data-testid={`daily-note-content-${note.id}`}
                            className={cn(
                              'max-h-48 overflow-y-auto whitespace-pre-wrap break-words text-sm',
                              note.is_done && 'text-muted-foreground line-through',
                            )}
                          >
                            {note.content || 'No details on this note.'}
                          </p>

                          {note.image_url ? (
                            <a
                              href={resolveMediaUrl(note.image_url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex text-sm text-primary underline"
                              data-testid={`daily-note-image-${note.id}`}
                            >
                              View image
                            </a>
                          ) : null}

                          {Array.isArray(note.checklist_items) &&
                          note.checklist_items.length > 0 ? (
                            <ul
                              className="space-y-1.5 rounded-md border bg-muted/30 px-2.5 py-2"
                              data-testid={`daily-note-checklist-${note.id}`}
                            >
                              {note.checklist_items.map((item) => {
                                const itemKey = `${note.id}:${item.id}`;
                                const canTick =
                                  canToggleDailyNote(note, currentUserId, viewAll) &&
                                  Boolean(item.id);
                                return (
                                  <li
                                    key={item.id || item.label}
                                    className="flex items-start gap-2 text-sm"
                                  >
                                    <input
                                      type="checkbox"
                                      className="mt-0.5 h-4 w-4 shrink-0"
                                      checked={Boolean(item.is_done)}
                                      disabled={
                                        !canTick || togglingChecklistKey === itemKey
                                      }
                                      onChange={() => onToggleChecklistItem?.(note, item)}
                                      aria-label={`Checklist: ${item.label}`}
                                      data-testid={`daily-note-checklist-item-${item.id}`}
                                    />
                                    <span
                                      className={cn(
                                        item.is_done &&
                                          'text-muted-foreground line-through'
                                      )}
                                    >
                                      {item.label}
                                    </span>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : null}

                          <div className="flex flex-wrap items-center gap-2">
                            {noticeRequiresSaleFix(note) ? null : (
                              <label className="flex items-center gap-2 text-sm">
                                <input
                                  type="checkbox"
                                  className="h-4 w-4 shrink-0"
                                  checked={Boolean(note.is_done)}
                                  disabled={
                                    !canToggleDailyNote(note, currentUserId, viewAll) ||
                                    togglingNoteId === note.id
                                  }
                                  onChange={() => onToggle(note)}
                                  aria-label={`Tick note ${note.title || note.id}`}
                                />
                                Mark done
                              </label>
                            )}
                            {isApprovalRejectionNote(note) &&
                            canResubmitRejection(
                              parseApprovalRejectionNotice(note.content),
                              note.content,
                              note.title
                            ) ? (
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={resubmittingKey === `note-${note.id}`}
                                onClick={() => onResubmit(note, 'note')}
                              >
                                <Redo2 className="h-3.5 w-3.5" />
                                {resubmittingKey === `note-${note.id}`
                                  ? 'Sending…'
                                  : 'Send back for approval'}
                              </Button>
                            ) : null}
                            {isApprovalRejectionNote(note) &&
                            rejectedSaleFixPath(
                              parseApprovalRejectionNotice(note.content),
                              note.title
                            ) ? (
                              <Button
                                type="button"
                                size="sm"
                                data-testid={`daily-note-open-sale-${note.id}`}
                                onClick={() => onFixSale?.(note)}
                              >
                                Open sale
                              </Button>
                            ) : null}
                          </div>

                          {isModuleFeatureEnabled('daily_notes', 'note_review', true) &&
                          note.is_done ? (
                            <NoteReviewBox
                              note={note}
                              currentUserId={currentUserId}
                              reviewers={reviewers}
                              canAsk={
                                note.author === currentUserId ||
                                note.author_id === currentUserId ||
                                note.assigned_to === currentUserId ||
                                viewAll
                              }
                              onRequestReview={onRequestReview}
                              onCompleteReview={onCompleteReview}
                            />
                          ) : null}

                          <div className="flex flex-wrap gap-1">
                            {NOTE_BOARD_COLUMNS.filter((item) => item.id !== column.id).map(
                              (item) => (
                                <Button
                                  key={item.id}
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  className="h-7 px-2 text-xs"
                                  data-testid={`daily-note-move-${note.id}-${item.id}`}
                                  onClick={() => onMove(note, item.id)}
                                >
                                  {item.title}
                                </Button>
                              )
                            )}
                            {canModifyEntry(note) ? (
                              <>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="ml-auto h-7 w-7"
                                  title="Edit"
                                  data-testid={`daily-note-edit-${note.id}`}
                                  onClick={() => onEdit(note)}
                                >
                                  <Pencil className="h-4 w-4" />
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  title="Delete"
                                  data-testid={`daily-note-delete-${note.id}`}
                                  onClick={() => onDelete(note.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </li>
                  );
                })
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function NoteReviewBox({
  note,
  currentUserId,
  reviewers,
  canAsk,
  onRequestReview,
  onCompleteReview,
}) {
  const [reviewerId, setReviewerId] = React.useState('');
  const [comment, setComment] = React.useState('');
  const reviews = Array.isArray(note.reviews) ? note.reviews : [];
  const mine = reviews.find(
    (row) => String(row.reviewer_id) === String(currentUserId) && row.status === 'pending'
  );

  const ask = () => {
    if (!reviewerId || !onRequestReview) return;
    onRequestReview(note, [Number(reviewerId)]);
  };

  const finish = () => {
    if (!mine || !onCompleteReview) return;
    onCompleteReview(note, mine.id, comment);
  };

  return (
    <div className="space-y-2 rounded-md border bg-muted/20 px-2.5 py-2" data-testid={`note-review-${note.id}`}>
      {reviews.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {reviews.map((row) => (
            <li key={row.id}>
              <span className="font-medium">{row.reviewer_name}</span>
              {row.status === 'pending' ? ' — waiting for their review' : ' — reviewed'}
              {row.comment ? <span className="block text-muted-foreground">{row.comment}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">
          Tag someone to look at this finished note and leave feedback.
        </p>
      )}
      {mine ? (
        <div className="space-y-2">
          <label className="block text-xs font-medium" htmlFor={`review-comment-${note.id}`}>
            Your feedback
          </label>
          <textarea
            id={`review-comment-${note.id}`}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm"
            maxLength={500}
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            data-testid={`note-review-comment-${note.id}`}
          />
          <Button type="button" size="sm" onClick={finish} data-testid={`note-review-finish-${note.id}`}>
            Mark reviewed
          </Button>
        </div>
      ) : null}
      {canAsk ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor={`review-person-${note.id}`}>
            Person to review
          </label>
          <select
            id={`review-person-${note.id}`}
            className="h-8 max-w-[14rem] rounded-md border bg-background px-2 text-sm"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
            data-testid={`note-review-person-${note.id}`}
          >
            <option value="">Choose a person</option>
            {reviewers.map((person) => (
              <option key={person.id} value={person.id}>
                {person.display_name || person.username}
              </option>
            ))}
          </select>
          <Button type="button" size="sm" variant="outline" disabled={!reviewerId} onClick={ask} data-testid={`note-review-ask-${note.id}`}>
            Ask them to review
          </Button>
        </div>
      ) : null}
    </div>
  );
}
