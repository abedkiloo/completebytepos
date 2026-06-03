/**
 * Shared client-side form validation and API error mapping.
 */

/** @returns {string|undefined} */
export function required(value, message = 'This field is required') {
  if (value === null || value === undefined) return message;
  if (typeof value === 'string' && !value.trim()) return message;
  return undefined;
}

/** @returns {string|undefined} */
export function minLength(value, min, message) {
  if (!value || String(value).length >= min) return undefined;
  return message || `Must be at least ${min} characters`;
}

/**
 * Map DRF error payloads to { fieldName: message }.
 * @param {object} data
 * @returns {Record<string, string>}
 */
export function normalizeApiErrors(data) {
  if (!data || typeof data !== 'object') return {};

  if (typeof data.error === 'string') {
    return { _form: data.error };
  }
  if (typeof data.detail === 'string') {
    return { _form: data.detail };
  }

  const errors = {};
  for (const [key, value] of Object.entries(data)) {
    if (key === 'error' || key === 'detail') continue;
    if (Array.isArray(value)) {
      errors[key] = value.join(' ');
    } else if (typeof value === 'string') {
      errors[key] = value;
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      for (const [nestedKey, nestedVal] of Object.entries(value)) {
        const msg = Array.isArray(nestedVal) ? nestedVal.join(' ') : String(nestedVal);
        errors[`${key}.${nestedKey}`] = msg;
        errors[nestedKey] = msg;
      }
    }
  }
  return errors;
}

export function hasValidationErrors(errors) {
  return errors && Object.keys(errors).length > 0;
}

export function firstErrorField(errors) {
  const key = Object.keys(errors).find((k) => k !== '_form');
  return key || null;
}

/**
 * @param {Record<string, string>} errors
 * @param {string} fieldName
 */
export function fieldError(errors, fieldName) {
  if (!errors) return undefined;
  return errors[fieldName] || errors[`profile.${fieldName}`];
}

export function formGroupClass(errors, fieldName, extra = '') {
  const err = fieldError(errors, fieldName);
  return ['form-group', err ? 'has-error field-error' : '', extra].filter(Boolean).join(' ');
}
