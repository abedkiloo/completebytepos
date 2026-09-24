import React from 'react';
import { Pencil, Redo2, Trash2 } from 'lucide-react';
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
  parseApprovalRejectionNotice,
} from '../../utils/approvalReturn';

export default function DailyNotesBoard({
  notes,
  viewAll,
  currentUserId,
  togglingNoteId,
  resubmittingKey,
  onToggle,
  onMove,
  onEdit,
  onDelete,
  onResubmit,
  canModifyEntry,
}) {
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
                cards.map((note) => (
                  <li
                    key={note.id}
                    className="rounded-lg border bg-background p-3 shadow-sm"
                  >
                    <div className="mb-2 flex items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 shrink-0"
                        checked={Boolean(note.is_done)}
                        disabled={
                          !canToggleDailyNote(note, currentUserId, viewAll) ||
                          togglingNoteId === note.id
                        }
                        onChange={() => onToggle(note)}
                        aria-label={`Tick note ${note.title || note.id}`}
                      />
                      <div className="min-w-0 flex-1">
                        <p
                          className={`text-sm font-semibold ${note.is_done ? 'text-muted-foreground line-through' : ''}`}
                        >
                          {note.title || 'Untitled note'}
                        </p>
                        <p
                          data-testid={`daily-note-content-${note.id}`}
                          className={`mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-sm ${note.is_done ? 'text-muted-foreground line-through' : ''}`}
                        >
                          {note.content}
                        </p>
                      </div>
                    </div>
                    <div className="mb-2 flex flex-wrap items-center gap-1">
                      <Badge variant={isStickyNote(note) ? 'destructive' : 'secondary'}>
                        {noteKindLabel(note)}
                      </Badge>
                      {viewAll && (note.author_name || note.assigned_to_name || note.assigned_role_name) ? (
                        <span className="text-xs text-muted-foreground">
                          {note.assigned_to_name || note.assigned_role_name
                            ? `For ${note.assigned_to_name || note.assigned_role_name}`
                            : note.author_name}
                        </span>
                      ) : null}
                    </div>
                    {isApprovalRejectionNote(note) &&
                    canResubmitRejection(parseApprovalRejectionNotice(note.content)) ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mb-2"
                        disabled={resubmittingKey === `note-${note.id}`}
                        onClick={() => onResubmit(note, 'note')}
                      >
                        <Redo2 className="h-3.5 w-3.5" />
                        {resubmittingKey === `note-${note.id}`
                          ? 'Sending…'
                          : 'Send back for approval'}
                      </Button>
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
                  </li>
                ))
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
