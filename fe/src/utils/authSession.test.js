import {
  isSessionTeardownActive,
  clearSessionTeardownFlag,
  isAuthenticated,
  clearAuthState,
  beginSessionTeardown,
  logoutLocally,
  logoutAndRedirect,
} from './authSession';
import { installLocalStorageMock, installSessionStorageMock } from '../test-utils';

describe('authSession', () => {
  beforeEach(() => {
    installLocalStorageMock();
    installSessionStorageMock();
    clearSessionTeardownFlag();
    localStorage.setItem('access_token', 'tok');
    localStorage.setItem('isAuthenticated', 'true');
  });

  it('isAuthenticated requires token and flag', () => {
    expect(isAuthenticated()).toBe(true);
    localStorage.removeItem('access_token');
    expect(isAuthenticated()).toBe(false);
  });

  it('beginSessionTeardown clears auth once', () => {
    expect(beginSessionTeardown()).toBe(true);
    expect(beginSessionTeardown()).toBe(false);
    expect(isSessionTeardownActive()).toBe(true);
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('clearAuthState removes keys', () => {
    clearAuthState();
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('logoutLocally clears session after revoke', async () => {
    localStorage.setItem('refresh_token', 'refresh');
    await logoutLocally();
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('logoutAndRedirect skips when already on login', async () => {
    const replace = jest.fn();
    delete window.location;
    window.location = { pathname: '/login', replace };
    await logoutAndRedirect();
    expect(replace).not.toHaveBeenCalled();
  });

  it('logoutAndRedirect with idle reason redirects to login with expired flag', async () => {
    const replace = jest.fn();
    delete window.location;
    window.location = { pathname: '/dashboard', replace };
    await logoutAndRedirect({ reason: 'idle' });
    expect(replace).toHaveBeenCalledWith('/login?expired=idle');
    expect(sessionStorage.getItem('session_expired_reason')).toBe('idle');
  });

  it('isAuthenticated is false during session teardown', () => {
    beginSessionTeardown();
    expect(isAuthenticated()).toBe(false);
  });
});
