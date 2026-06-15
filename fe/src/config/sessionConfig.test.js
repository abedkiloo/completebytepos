import {
  SESSION_IDLE_MINUTES,
  SESSION_IDLE_MS,
  ACTIVITY_PERSIST_INTERVAL_MINUTES,
  ACTIVITY_PERSIST_INTERVAL_MS,
  sessionIdleExpiredMessage,
} from './sessionConfig';

describe('sessionConfig', () => {
  test('idle timeout is thirty minutes', () => {
    expect(SESSION_IDLE_MINUTES).toBe(30);
    expect(SESSION_IDLE_MS).toBe(30 * 60 * 1000);
  });

  test('activity is persisted at most every five minutes', () => {
    expect(ACTIVITY_PERSIST_INTERVAL_MINUTES).toBe(5);
    expect(ACTIVITY_PERSIST_INTERVAL_MS).toBe(5 * 60 * 1000);
  });

  test('sessionIdleExpiredMessage references configured minutes', () => {
    expect(sessionIdleExpiredMessage()).toContain('30 minutes');
  });
});
