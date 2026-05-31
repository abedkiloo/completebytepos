/**
 * Log out after a period of user inactivity (mouse, keyboard, touch, scroll).
 * Activity is shared across tabs via localStorage.
 */
import { isAuthenticated, logoutAndRedirect, isSessionTeardownActive } from './authSession';

/** 5 minutes without interaction → session ends. */
export const SESSION_IDLE_MS = 5 * 60 * 1000;

const CHECK_INTERVAL_MS = 15 * 1000;
const ACTIVITY_THROTTLE_MS = 1000;
const LAST_ACTIVITY_KEY = 'last_activity_at';

const ACTIVITY_EVENTS = [
  'mousedown',
  'mousemove',
  'keydown',
  'touchstart',
  'scroll',
  'click',
];

let checkTimer = null;
let listenersAttached = false;
let lastMark = 0;

export function markSessionActivity() {
  if (!isAuthenticated()) return;
  const now = Date.now();
  if (now - lastMark < ACTIVITY_THROTTLE_MS) return;
  lastMark = now;
  localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
}

function onStorageSync(event) {
  if (event.key === LAST_ACTIVITY_KEY) return;
  if (event.key === 'access_token' && !event.newValue) {
    stopIdleSessionWatch();
    if (!isSessionTeardownActive()) {
      logoutAndRedirect({ reason: 'idle' });
    }
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') {
    checkIdleTimeout();
  }
}

function checkIdleTimeout() {
  if (!isAuthenticated()) return;

  const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || 0);
  if (!last) {
    markSessionActivity();
    return;
  }

  if (Date.now() - last >= SESSION_IDLE_MS) {
    stopIdleSessionWatch();
    logoutAndRedirect({ reason: 'idle' });
  }
}

export function startIdleSessionWatch() {
  if (!isAuthenticated()) return;

  markSessionActivity();

  if (!listenersAttached) {
    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, markSessionActivity, { passive: true });
    });
    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('storage', onStorageSync);
    listenersAttached = true;
  }

  if (!checkTimer) {
    checkTimer = setInterval(checkIdleTimeout, CHECK_INTERVAL_MS);
  }
}

export function stopIdleSessionWatch() {
  if (checkTimer) {
    clearInterval(checkTimer);
    checkTimer = null;
  }

  if (!listenersAttached) {
    lastMark = 0;
    return;
  }

  ACTIVITY_EVENTS.forEach((eventName) => {
    window.removeEventListener(eventName, markSessionActivity);
  });
  document.removeEventListener('visibilitychange', onVisibilityChange);
  window.removeEventListener('storage', onStorageSync);
  listenersAttached = false;
  lastMark = 0;
}

export function getIdleRemainingMs() {
  const last = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || Date.now());
  return Math.max(0, SESSION_IDLE_MS - (Date.now() - last));
}
