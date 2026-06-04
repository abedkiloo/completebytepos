import {
  SESSION_IDLE_MS,
  markSessionActivity,
  getIdleRemainingMs,
  startIdleSessionWatch,
  stopIdleSessionWatch,
} from './sessionIdle';
import { clearAuthState, clearSessionTeardownFlag } from './authSession';

jest.mock('./authSession', () => {
  const actual = jest.requireActual('./authSession');
  return {
    ...actual,
    logoutAndRedirect: jest.fn(() => Promise.resolve()),
    isSessionTeardownActive: jest.fn(() => false),
  };
});

const { logoutAndRedirect } = require('./authSession');

describe('sessionIdle', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    localStorage.clear();
    clearSessionTeardownFlag();
    stopIdleSessionWatch();
    logoutAndRedirect.mockClear();
    localStorage.setItem('access_token', 'test-token');
    localStorage.setItem('isAuthenticated', 'true');
  });

  afterEach(() => {
    jest.useRealTimers();
    stopIdleSessionWatch();
    clearAuthState();
    sessionStorage.clear();
  });

  test('SESSION_IDLE_MS is fifteen minutes', () => {
    expect(SESSION_IDLE_MS).toBe(15 * 60 * 1000);
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

  test('checkIdleTimeout logs out after idle period', () => {
    startIdleSessionWatch();
    localStorage.setItem('last_activity_at', String(Date.now() - SESSION_IDLE_MS - 1000));
    jest.advanceTimersByTime(20_000);
    expect(logoutAndRedirect).toHaveBeenCalledWith({ reason: 'idle' });
    stopIdleSessionWatch();
  });

  test('checkIdleTimeout does not logout before idle period ends', () => {
    startIdleSessionWatch();
    localStorage.setItem(
      'last_activity_at',
      String(Date.now() - SESSION_IDLE_MS + 60_000)
    );
    jest.advanceTimersByTime(20_000);
    expect(logoutAndRedirect).not.toHaveBeenCalled();
    stopIdleSessionWatch();
  });
});
