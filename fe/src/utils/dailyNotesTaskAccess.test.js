import {
  canEditDailyTask,
  canToggleDailyTask,
  isPendingTasksPromptDismissed,
  isTaskAssignee,
  isTaskAuthor,
  markPendingTasksPromptDismissed,
  clearPendingTasksPromptDismissed,
} from './dailyNotesTaskAccess';

describe('dailyNotesTaskAccess', () => {
  const task = {
    id: 1,
    author_id: 10,
    assigned_to_id: 20,
  };

  test('canToggleDailyTask allows assignee and author', () => {
    expect(canToggleDailyTask(task, 20)).toBe(true);
    expect(canToggleDailyTask(task, 10)).toBe(true);
    expect(canToggleDailyTask(task, 99)).toBe(false);
  });

  test('canEditDailyTask allows author or viewAll', () => {
    expect(canEditDailyTask(task, 10)).toBe(true);
    expect(canEditDailyTask(task, 20, false)).toBe(false);
    expect(canEditDailyTask(task, 20, true)).toBe(true);
  });

  test('identity helpers', () => {
    expect(isTaskAuthor(task, 10)).toBe(true);
    expect(isTaskAssignee(task, 20)).toBe(true);
  });

  test('pending prompt session flag', () => {
    clearPendingTasksPromptDismissed();
    expect(isPendingTasksPromptDismissed()).toBe(false);
    markPendingTasksPromptDismissed();
    expect(isPendingTasksPromptDismissed()).toBe(true);
    clearPendingTasksPromptDismissed();
  });
});
