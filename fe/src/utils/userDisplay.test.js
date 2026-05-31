import { usersShowEmail, usersShowStatus } from './userDisplay';

describe('userDisplay', () => {
  test('email default on', () => {
    expect(usersShowEmail({})).toBe(true);
  });

  test('status respects hide_entity_status_toggles', () => {
    expect(usersShowStatus({ show_user_status: true }, { hide_entity_status_toggles: true })).toBe(
      false
    );
  });
});
