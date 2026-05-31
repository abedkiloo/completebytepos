import {
  SESSION_IDLE_MS,
  markSessionActivity,
  getIdleRemainingMs,
  startIdleSessionWatch,
  stopIdleSessionWatch,
} from './sessionIdle';
import { clearAuthState } from './authSession';

describe('sessionIdle', () => {
  beforeEach(() => {
    localStorage.clear();
    stopIdleSessionWatch();
    localStorage.setItem('access_token', 'test-token');
    localStorage.setItem('isAuthenticated', 'true');
  });

  afterEach(() => {
    stopIdleSessionWatch();
    clearAuthState();
    sessionStorage.clear();
  });

  test('SESSION_IDLE_MS is five minutes', () => {
    expect(SESSION_IDLE_MS).toBe(5 * 60 * 1000);
  });

  test('markSessionActivity updates last_activity_at', () => {
    markSessionActivity();
    expect(localStorage.getItem('last_activity_at')).toBeTruthy();
  });

  test('getIdleRemainingMs decreases as time passes', () => {
    localStorage.setItem('last_activity_at', String(Date.now() - 60_000));
    const remaining = getIdleRemainingMs();
    expect(remaining).toBeLessThanOrEqual(SESSION_IDLE_MS - 60_000);
    expect(remaining).toBeGreaterThan(0);
  });

  test('startIdleSessionWatch sets activity timestamp', () => {
    startIdleSessionWatch();
    expect(localStorage.getItem('last_activity_at')).toBeTruthy();
    stopIdleSessionWatch();
  });
});
