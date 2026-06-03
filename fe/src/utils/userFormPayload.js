/**
 * User form payload builder + client validation (mirrors admin user API).
 */

import { required, minLength } from './formValidation';

export function buildUserPayload(formData, options) {
  const {
    isEdit,
    showEmail,
    showFullName,
    showPhone,
    showStaffFlag,
    hideStatusToggles,
    showInlineRoles,
  } = options;

  const payload = {};

  if (!isEdit) {
    payload.username = formData.username.trim();
    if (formData.password) {
      payload.password = formData.password;
    }
  }

  if (showEmail) {
    payload.email = formData.email.trim();
  }
  if (showFullName) {
    payload.first_name = formData.first_name.trim();
    payload.last_name = formData.last_name.trim();
  }
  if (showStaffFlag) {
    payload.is_staff = formData.is_staff;
  }
  if (!hideStatusToggles) {
    payload.is_active = formData.is_active;
  }
  if (showInlineRoles) {
    payload.role = formData.role;
    payload.custom_role_id = formData.custom_role_id
      ? parseInt(formData.custom_role_id, 10)
      : null;
  }
  if (showPhone) {
    payload.phone_number = formData.phone_number.trim();
  }

  return payload;
}

export function validateUserForm(formData, options) {
  const { isEdit, showEmail } = options;
  const errors = {};

  const usernameErr = required(formData.username, 'Username is required');
  if (usernameErr) errors.username = usernameErr;

  if (!isEdit) {
    const passwordErr = required(formData.password, 'Password is required');
    if (passwordErr) {
      errors.password = passwordErr;
    } else {
      const minErr = minLength(
        formData.password,
        6,
        'Password must be at least 6 characters'
      );
      if (minErr) errors.password = minErr;
    }
  }

  if (showEmail && formData.email.trim()) {
    const email = formData.email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Enter a valid email address';
    }
  }

  return errors;
}
