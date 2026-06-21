/**
 * Daily task permission helpers (mirrors backend assignee rules).
 */

export function isTaskAuthor(task, userId) {
  if (!task || userId == null) return false;
  return task.author === userId || task.author_id === userId;
}

export function isTaskAssignee(task, userId) {
  if (!task || userId == null) return false;
  return task.assigned_to === userId || task.assigned_to_id === userId;
}

/** Assignee (or author) may mark done / reopen. */
export function canToggleDailyTask(task, userId) {
  return isTaskAssignee(task, userId) || isTaskAuthor(task, userId);
}

/** Creator or staff with view-all may edit/delete. */
export function canEditDailyTask(task, userId, viewAll = false) {
  if (viewAll) return true;
  return isTaskAuthor(task, userId);
}

export const PENDING_TASKS_PROMPT_KEY = 'pending_tasks_prompt_dismissed';

export function clearPendingTasksPromptDismissed() {
  try {
    sessionStorage.removeItem(PENDING_TASKS_PROMPT_KEY);
  } catch {
    /* ignore */
  }
}

export function markPendingTasksPromptDismissed() {
  try {
    sessionStorage.setItem(PENDING_TASKS_PROMPT_KEY, '1');
  } catch {
    /* ignore */
  }
}

export function isPendingTasksPromptDismissed() {
  try {
    return sessionStorage.getItem(PENDING_TASKS_PROMPT_KEY) === '1';
  } catch {
    return false;
  }
}
