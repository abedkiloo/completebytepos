import {
  SESSION_IDLE_MS,
  ACTIVITY_PERSIST_INTERVAL_MS,
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
    jest.useFakeTimers({ advanceTime: false });
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

  test('SESSION_IDLE_MS is thirty minutes', () => {
    expect(SESSION_IDLE_MS).toBe(30 * 60 * 1000);
  });

  test('markSessionActivity updates last_activity_at', () => {
    markSessionActivity();
    expect(localStorage.getItem('last_activity_at')).toBeTruthy();
  });

  test('activity timestamp updates at most every five minutes while active', () => {
    const start = Date.now();
    jest.setSystemTime(start);
    markSessionActivity();
    const first = localStorage.getItem('last_activity_at');

    jest.setSystemTime(start + 2 * 60 * 1000);
    markSessionActivity();
    expect(localStorage.getItem('last_activity_at')).toBe(first);

    jest.setSystemTime(start + ACTIVITY_PERSIST_INTERVAL_MS + 1);
    markSessionActivity();
    expect(Number(localStorage.getItem('last_activity_at'))).toBeGreaterThan(Number(first));
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
    jest.advanceTimersByTime(60_000);
    expect(logoutAndRedirect).toHaveBeenCalledWith({ reason: 'idle' });
    stopIdleSessionWatch();
  });

  test('activity before idle deadline pushes logout forward', () => {
    const start = Date.now();
    jest.setSystemTime(start);
    localStorage.setItem('last_activity_at', String(start));
    startIdleSessionWatch();
    logoutAndRedirect.mockClear();

    jest.setSystemTime(start + 28 * 60 * 1000);
    jest.advanceTimersByTime(60_000);
    expect(logoutAndRedirect).not.toHaveBeenCalled();

    jest.setSystemTime(start + 29 * 60 * 1000);
    markSessionActivity();
    logoutAndRedirect.mockClear();
    jest.advanceTimersByTime(60_000);
    expect(logoutAndRedirect).not.toHaveBeenCalled();

    const activeAt = Number(localStorage.getItem('last_activity_at'));
    jest.setSystemTime(activeAt + SESSION_IDLE_MS + 1000);
    jest.advanceTimersByTime(60_000);
    expect(logoutAndRedirect).toHaveBeenCalledWith({ reason: 'idle' });
    stopIdleSessionWatch();
  });

  test('checkIdleTimeout does not logout before idle period ends', () => {
    startIdleSessionWatch();
    localStorage.setItem(
      'last_activity_at',
      String(Date.now() - SESSION_IDLE_MS + 5 * 60_000)
    );
    jest.advanceTimersByTime(60_000);
    expect(logoutAndRedirect).not.toHaveBeenCalled();
    stopIdleSessionWatch();
  });

  test('markSessionActivity skips when not authenticated', () => {
    localStorage.removeItem('access_token');
    markSessionActivity();
    expect(localStorage.getItem('last_activity_at')).toBeNull();
  });

  test('storage event clearing access_token triggers idle logout', () => {
    startIdleSessionWatch();
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: 'access_token',
        newValue: null,
        oldValue: 'test-token',
      })
    );
    expect(logoutAndRedirect).toHaveBeenCalledWith({ reason: 'idle' });
    stopIdleSessionWatch();
  });
});
