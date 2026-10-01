import {
  canShowAppraisalGreetingOverlay,
  canShowPendingTasksOverlay,
  getLoginOverlayState,
  resetLoginOverlayQueue,
  setPendingTasksOverlay,
  setStickyNotesOverlay,
  subscribeLoginOverlay,
} from './loginOverlayQueue';

describe('loginOverlayQueue', () => {
  afterEach(() => {
    resetLoginOverlayQueue();
  });

  it('holds pending tasks and greeting until sticky notes finish', () => {
    setStickyNotesOverlay({ loading: true, open: false });
    expect(canShowPendingTasksOverlay()).toBe(false);
    expect(canShowAppraisalGreetingOverlay()).toBe(false);

    setStickyNotesOverlay({ loading: false, open: true });
    expect(canShowPendingTasksOverlay()).toBe(false);
    expect(canShowAppraisalGreetingOverlay()).toBe(false);

    setStickyNotesOverlay({ loading: false, open: false });
    expect(canShowPendingTasksOverlay()).toBe(true);
    expect(canShowAppraisalGreetingOverlay()).toBe(true);
  });

  it('holds greeting until the welcome summary is done', () => {
    setPendingTasksOverlay({ loading: true, open: false });
    expect(canShowPendingTasksOverlay()).toBe(true);
    expect(canShowAppraisalGreetingOverlay()).toBe(false);

    setPendingTasksOverlay({ loading: false, open: true });
    expect(canShowAppraisalGreetingOverlay()).toBe(false);

    setPendingTasksOverlay({ loading: false, open: false });
    expect(canShowAppraisalGreetingOverlay()).toBe(true);
  });

  it('notifies subscribers and ignores unchanged patches', () => {
    const seen = [];
    const stop = subscribeLoginOverlay((next) => seen.push(next));
    setStickyNotesOverlay({ loading: true });
    setStickyNotesOverlay({ loading: true });
    expect(seen.filter((row) => row.stickyLoading).length).toBe(1);
    expect(getLoginOverlayState().stickyLoading).toBe(true);
    stop();
    setStickyNotesOverlay({ loading: false });
    expect(seen[seen.length - 1].stickyLoading).toBe(true);
  });
});
