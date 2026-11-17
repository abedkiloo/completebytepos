/**
 * User form payload builder + client validation (mirrors admin user API).
 *
 * Username is sent on create and on edit. Length 1–150 after trim.
 */

import { required, minLength, emailMessage, phoneMessage } from './formValidation';

/**
 * Build the user create/update body.
 *
 * @param {object} formData Form fields. `username` is trimmed to 1–150 characters.
 * @param {object} options Visibility flags. `isEdit` keeps a blank password off the body.
 * @returns {object} API payload. Always includes `username` when the form has one.
 */
export function buildUserPayload(formData, options) {
  const {
    showEmail,
    showFullName,
    showPhone,
    showStaffFlag,
    hideStatusToggles,
    showInlineRoles,
  } = options;

  const payload = {
    username: (formData.username || '').trim(),
  };

  if (formData.password) {
    payload.password = formData.password;
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

/**
 * Check the user form before it is submitted.
 *
 * @param {object} formData Form fields. Username is required, 1–150 after trim.
 * @param {object} options `isEdit` skips the password when it is left blank.
 * @returns {object} Field errors. Empty object when the form can be saved.
 */
export function validateUserForm(formData, options) {
  const { isEdit, showEmail, showPhone } = options;
  const errors = {};

  const username = (formData.username || '').trim();
  const usernameErr = required(username, 'Enter a username, e.g. jane.wambua');
  if (usernameErr) errors.username = usernameErr;
  else if (username.length > 150) errors.username = 'Username must be 1–150 characters.';

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
  } else if (formData.password) {
    const minErr = minLength(
      formData.password,
      6,
      'Password must be at least 6 characters'
    );
    if (minErr) errors.password = minErr;
  }

  if (showEmail && formData.email.trim()) {
    const emailErr = emailMessage(formData.email);
    if (emailErr) errors.email = emailErr;
  }

  if (showPhone) {
    const phoneErr = phoneMessage(formData.phone_number);
    if (phoneErr) errors.phone_number = phoneErr;
  }

  return errors;
}
