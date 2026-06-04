import {
  SESSION_IDLE_MINUTES,
  SESSION_IDLE_MS,
  sessionIdleExpiredMessage,
} from './sessionConfig';

describe('sessionConfig', () => {
  test('idle timeout is fifteen minutes', () => {
    expect(SESSION_IDLE_MINUTES).toBe(15);
    expect(SESSION_IDLE_MS).toBe(15 * 60 * 1000);
  });

  test('sessionIdleExpiredMessage references configured minutes', () => {
    expect(sessionIdleExpiredMessage()).toContain('15 minutes');
  });
});
