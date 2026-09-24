/**
 * Notes that must be ticked block the assignee. Other notes never block.
 */

export function isStickyNote(note) {
  return Boolean(note?.is_sticky);
}

export function isGeneralNote(note) {
  return !isStickyNote(note);
}

export function isNoteDone(note) {
  return Boolean(note?.is_done);
}

export function unresolvedStickyNotes(notes = []) {
  return (Array.isArray(notes) ? notes : []).filter(
    (note) => isStickyNote(note) && !isNoteDone(note),
  );
}

export function hasBlockingStickyNotes(notes = []) {
  return unresolvedStickyNotes(notes).length > 0;
}

export function unresolvedInboxNotes(notes = []) {
  return (Array.isArray(notes) ? notes : []).filter((note) => !isNoteDone(note));
}

export function hasInboxNotes(notes = []) {
  return unresolvedInboxNotes(notes).length > 0;
}

export function canEditDailyNote(note, userId) {
  return isNoteAuthor(note, userId);
}

export function noteKindLabel(note) {
  return isStickyNote(note) ? 'Must tick' : 'Note';
}

export function noteBoardColumn(note) {
  const raw = (note?.board_column || '').toString().trim().toLowerCase();
  if (raw === 'todo' || raw === 'doing' || raw === 'past') return raw;
  if (isNoteDone(note)) return 'past';
  if (note?.in_progress) return 'doing';
  return 'todo';
}

export function notesForBoardColumn(notes = [], column) {
  return (Array.isArray(notes) ? notes : []).filter(
    (note) => noteBoardColumn(note) === column,
  );
}

export const NOTE_BOARD_COLUMNS = [
  { id: 'todo', title: 'To do' },
  { id: 'doing', title: 'Doing' },
  { id: 'past', title: 'Past' },
];

export function isNoteAuthor(note, userId) {
  if (!note || userId == null) return false;
  return note.author === userId || note.author_id === userId;
}

export function isNoteAssignee(note, userId) {
  if (!note || userId == null) return false;
  return note.assigned_to === userId || note.assigned_to_id === userId;
}

/** Assignee, author, or admin (view-all) may tick / untick. */
export function canToggleDailyNote(note, userId, viewAll = false) {
  if (viewAll) return true;
  return isNoteAuthor(note, userId) || isNoteAssignee(note, userId);
}

export function sortDailyNotes(notes = []) {
  return [...(Array.isArray(notes) ? notes : [])].sort((a, b) => {
    const stickyDelta = Number(isStickyNote(b)) - Number(isStickyNote(a));
    if (stickyDelta) return stickyDelta;
    const doneDelta = Number(isNoteDone(a)) - Number(isNoteDone(b));
    if (doneDelta) return doneDelta;
    return String(b.created_at || '').localeCompare(String(a.created_at || ''));
  });
}
