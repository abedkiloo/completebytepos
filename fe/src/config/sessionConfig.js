/**
 * Client idle timeout — keep aligned with JWT_ACCESS_TOKEN_MINUTES in backend .env.
 *
 * Logout happens after SESSION_IDLE_MINUTES with no activity. While the user
 * is active, last_activity_at is updated at most every ACTIVITY_PERSIST_INTERVAL
 * minutes so the deadline slides forward (e.g. login 7:00 → logout 7:30; still
 * active at 7:30 → logout 8:00).
 */
export const SESSION_IDLE_MINUTES = 30;

export const ACTIVITY_PERSIST_INTERVAL_MINUTES = 5;

export const SESSION_IDLE_MS = SESSION_IDLE_MINUTES * 60 * 1000;

export const ACTIVITY_PERSIST_INTERVAL_MS =
  ACTIVITY_PERSIST_INTERVAL_MINUTES * 60 * 1000;

export function sessionIdleExpiredMessage() {
  return `Your session expired after ${SESSION_IDLE_MINUTES} minutes of inactivity. Please sign in again.`;
}
