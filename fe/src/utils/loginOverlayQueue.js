/**
 * Login overlays must appear one at a time so dialogs cannot trap each other.
 * Priority: sticky notes (blocking work) > pending-task summary > appraisal greeting.
 */

const EMPTY = {
  stickyLoading: false,
  stickyOpen: false,
  pendingLoading: false,
  pendingOpen: false,
};

let state = { ...EMPTY };
const listeners = new Set();

function notify() {
  listeners.forEach((fn) => fn(getLoginOverlayState()));
}

export function getLoginOverlayState() {
  return { ...state };
}

export function subscribeLoginOverlay(listener) {
  listeners.add(listener);
  listener(getLoginOverlayState());
  return () => listeners.delete(listener);
}

export function resetLoginOverlayQueue() {
  state = { ...EMPTY };
  notify();
}

function assignOverlay(patch) {
  const next = { ...state, ...patch };
  if (
    next.stickyLoading === state.stickyLoading &&
    next.stickyOpen === state.stickyOpen &&
    next.pendingLoading === state.pendingLoading &&
    next.pendingOpen === state.pendingOpen
  ) {
    return;
  }
  state = next;
  notify();
}

export function setStickyNotesOverlay({ loading = false, open = false } = {}) {
  assignOverlay({
    stickyLoading: Boolean(loading),
    stickyOpen: Boolean(open),
  });
}

export function setPendingTasksOverlay({ loading = false, open = false } = {}) {
  assignOverlay({
    pendingLoading: Boolean(loading),
    pendingOpen: Boolean(open),
  });
}

export function canShowPendingTasksOverlay(snapshot = state) {
  return !snapshot.stickyLoading && !snapshot.stickyOpen;
}

export function canShowAppraisalGreetingOverlay(snapshot = state) {
  return canShowPendingTasksOverlay(snapshot) && !snapshot.pendingLoading && !snapshot.pendingOpen;
}
