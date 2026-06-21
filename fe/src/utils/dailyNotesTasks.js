/**
 * Daily task list helpers (sorting, labels, completion).
 */

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function taskCreatedTime(task) {
  const parsed = Date.parse(task?.created_at);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortDailyTasks(tasks = []) {
  return [...tasks].sort((a, b) => {
    if (Boolean(a.is_done) !== Boolean(b.is_done)) {
      return Number(a.is_done) - Number(b.is_done);
    }
    return taskCreatedTime(b) - taskCreatedTime(a);
  });
}

export function countOpenTasks(tasks = []) {
  return tasks.filter((t) => !t.is_done).length;
}

export function formatTaskCompletedAt(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return iso;
  }
}

export function taskStatusLabel(task) {
  if (!task?.is_done) return 'To do';
  const when = formatTaskCompletedAt(task.completed_at);
  return when ? `Done ${when}` : 'Done';
}

export function mergeActivityDates(noteDates = [], taskDates = []) {
  const dates = [...asArray(noteDates), ...asArray(taskDates)];
  return [...new Set(dates)].sort((a, b) => b.localeCompare(a));
}

export function formatDisplayDate(iso) {
  if (!iso) return '';
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}
