import { buildUserPayload, validateUserForm } from './userFormPayload';

const baseForm = {
  username: 'newuser',
  email: 'u@test.com',
  first_name: 'A',
  last_name: 'B',
  password: 'secret12',
  is_staff: false,
  is_active: true,
  role: 'cashier',
  custom_role_id: '3',
  phone_number: '2547',
};

const allOptions = {
  isEdit: false,
  showEmail: true,
  showFullName: true,
  showPhone: true,
  showStaffFlag: true,
  hideStatusToggles: false,
  showInlineRoles: true,
};

describe('userFormPayload', () => {
  describe('buildUserPayload', () => {
    it('includes username and password on create', () => {
      const payload = buildUserPayload(baseForm, allOptions);
      expect(payload.username).toBe('newuser');
      expect(payload.password).toBe('secret12');
      expect(payload.custom_role_id).toBe(3);
    });

    it('omits password on edit', () => {
      const payload = buildUserPayload(
        { ...baseForm, password: '' },
        { ...allOptions, isEdit: true }
      );
      expect(payload.password).toBeUndefined();
      expect(payload.username).toBeUndefined();
    });

    it('nulls custom_role_id when empty', () => {
      const payload = buildUserPayload(
        { ...baseForm, custom_role_id: '' },
        allOptions
      );
      expect(payload.custom_role_id).toBeNull();
    });
  });

  describe('validateUserForm', () => {
    it('requires username', () => {
      const errors = validateUserForm(
        { ...baseForm, username: '  ' },
        allOptions
      );
      expect(errors.username).toBeDefined();
    });

    it('requires password on create', () => {
      const errors = validateUserForm(
        { ...baseForm, password: '' },
        allOptions
      );
      expect(errors.password).toBeDefined();
    });

    it('skips password on edit', () => {
      const errors = validateUserForm(
        { ...baseForm, password: '' },
        { ...allOptions, isEdit: true }
      );
      expect(errors.password).toBeUndefined();
    });

    it('validates email format when provided', () => {
      const errors = validateUserForm(
        { ...baseForm, email: 'not-an-email' },
        allOptions
      );
      expect(errors.email).toBeDefined();
    });
  });
});
