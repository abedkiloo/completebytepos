/**
 * Sticky vs general daily notes.
 * Sticky notes block the assignee until ticked. General notes never block.
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

export function noteKindLabel(note) {
  return isStickyNote(note) ? 'Sticky' : 'General';
}

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
