/**
 * Client idle timeout — keep aligned with JWT_ACCESS_TOKEN_MINUTES in backend .env.
 */
export const SESSION_IDLE_MINUTES = 15;

export const SESSION_IDLE_MS = SESSION_IDLE_MINUTES * 60 * 1000;

export function sessionIdleExpiredMessage() {
  return `Your session expired after ${SESSION_IDLE_MINUTES} minutes of inactivity. Please sign in again.`;
}
