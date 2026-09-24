import {
  canEditDailyNote,
  canToggleDailyNote,
  hasBlockingStickyNotes,
  hasInboxNotes,
  isGeneralNote,
  isNoteAssignee,
  isNoteAuthor,
  isNoteDone,
  isStickyNote,
  NOTE_BOARD_COLUMNS,
  noteBoardColumn,
  noteKindLabel,
  notesForBoardColumn,
  sortDailyNotes,
  unresolvedInboxNotes,
  unresolvedStickyNotes,
} from './dailyNotesSticky';

describe('dailyNotesSticky', () => {
  const stickyOpen = {
    id: 1,
    is_sticky: true,
    is_done: false,
    author_id: 10,
    assigned_to_id: 20,
    created_at: '2026-09-24T10:00:00Z',
  };
  const generalDone = {
    id: 2,
    is_sticky: false,
    is_done: true,
    author: 10,
    created_at: '2026-09-24T11:00:00Z',
  };

  test('kind helpers and blocking list', () => {
    expect(isStickyNote(stickyOpen)).toBe(true);
    expect(isGeneralNote(stickyOpen)).toBe(false);
    expect(isGeneralNote(generalDone)).toBe(true);
    expect(isNoteDone(generalDone)).toBe(true);
    expect(noteKindLabel(stickyOpen)).toBe('Must tick');
    expect(noteKindLabel(generalDone)).toBe('Note');
    expect(unresolvedStickyNotes([stickyOpen, generalDone])).toEqual([stickyOpen]);
    expect(hasBlockingStickyNotes([stickyOpen])).toBe(true);
    expect(hasBlockingStickyNotes([generalDone])).toBe(false);
    expect(unresolvedStickyNotes(null)).toEqual([]);
    const generalOpen = { ...generalDone, is_done: false, assigned_to: 20 };
    expect(hasInboxNotes([stickyOpen, generalOpen])).toBe(true);
    expect(hasInboxNotes([generalDone])).toBe(false);
    expect(unresolvedInboxNotes(null)).toEqual([]);
    expect(canEditDailyNote(stickyOpen, 10)).toBe(true);
    expect(canEditDailyNote(stickyOpen, 20)).toBe(false);
  });

  test('tick permission', () => {
    expect(canToggleDailyNote(stickyOpen, 20)).toBe(true);
    expect(canToggleDailyNote(stickyOpen, 10)).toBe(true);
    expect(canToggleDailyNote(stickyOpen, 99)).toBe(false);
    expect(canToggleDailyNote(stickyOpen, 99, true)).toBe(true);
    expect(isNoteAuthor(stickyOpen, 10)).toBe(true);
    expect(isNoteAssignee(stickyOpen, 20)).toBe(true);
    expect(canToggleDailyNote(null, 10)).toBe(false);
  });

  test('sorts sticky open notes first then open before done', () => {
    const sorted = sortDailyNotes([generalDone, stickyOpen]);
    expect(sorted[0].id).toBe(1);
    const older = { ...stickyOpen, id: 3, created_at: '2026-09-24T09:00:00Z' };
    const newer = { ...stickyOpen, id: 4, created_at: '2026-09-24T12:00:00Z' };
    expect(sortDailyNotes([older, newer])[0].id).toBe(4);
    expect(sortDailyNotes([generalDone, { ...generalDone, id: 9, is_done: false }])[0].is_done).toBe(false);
    expect(sortDailyNotes()).toEqual([]);
  });

  test('maps notes onto To do, Doing, and Past columns', () => {
    expect(noteBoardColumn({ is_done: true })).toBe('past');
    expect(noteBoardColumn({ in_progress: true })).toBe('doing');
    expect(noteBoardColumn({ board_column: 'DOING' })).toBe('doing');
    expect(noteBoardColumn({})).toBe('todo');
    const rows = [
      { id: 1, is_done: false },
      { id: 2, in_progress: true },
      { id: 3, is_done: true },
    ];
    expect(notesForBoardColumn(rows, 'todo').map((n) => n.id)).toEqual([1]);
    expect(notesForBoardColumn(rows, 'doing').map((n) => n.id)).toEqual([2]);
    expect(notesForBoardColumn(rows, 'past').map((n) => n.id)).toEqual([3]);
    expect(notesForBoardColumn(null, 'todo')).toEqual([]);
    expect(NOTE_BOARD_COLUMNS.map((c) => c.id)).toEqual(['todo', 'doing', 'past']);
  });
});
