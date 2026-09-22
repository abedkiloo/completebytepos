/**
 * Shared client-side form validation and API error mapping.
 */

export const AMOUNT_EXAMPLE = '250.00';
export const MPESA_RECEIPT_EXAMPLE = 'QHX7K2L9M1';
export const MPESA_RECEIPT_LENGTH = 10;
export const EMAIL_EXAMPLE = 'name@example.com';
export const PHONE_EXAMPLE = '0712 345 678';
export const DATE_EXAMPLE = '2026-09-22';
export const QUANTITY_EXAMPLE = '3';
export const NAME_EXAMPLE = 'Jane Wambua';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MONEY_RE = /^\d+(\.\d{1,2})?$/;
const SIGNED_MONEY_RE = /^-?\d+(\.\d{1,2})?$/;
const INT_RE = /^-?\d+$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

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

export function normalizePaymentAmountInput(value) {
  return String(value ?? '').trim().replace(/,/g, '');
}

/**
 * @param {unknown} value
 * @param {{ required?: boolean, allowZero?: boolean, allowNegative?: boolean, label?: string }} [options]
 * @returns {string|undefined}
 */
export function moneyMessage(value, options = {}) {
  const {
    required: isRequired = true,
    allowZero = false,
    allowNegative = false,
    label = 'KES amount',
  } = options;
  const text = normalizePaymentAmountInput(value);
  if (!text) {
    if (!isRequired) return undefined;
    return `Enter a ${label}, e.g. ${AMOUNT_EXAMPLE}`;
  }
  const pattern = allowNegative ? SIGNED_MONEY_RE : MONEY_RE;
  if (!pattern.test(text)) {
    return `Use numbers only, up to 2 decimal places, e.g. ${AMOUNT_EXAMPLE}`;
  }
  const amount = Number(text);
  if (!allowNegative && amount < 0) {
    return `Amount cannot be negative, e.g. ${AMOUNT_EXAMPLE}`;
  }
  if (!allowZero && !(amount > 0)) {
    return `Amount must be greater than zero, e.g. ${AMOUNT_EXAMPLE}`;
  }
  return undefined;
}

/** @returns {string|undefined} */
export function paymentAmountMessage(value) {
  return moneyMessage(value, { allowZero: false });
}

export function parsePaymentAmount(value) {
  if (paymentAmountMessage(value)) return undefined;
  return Number(normalizePaymentAmountInput(value));
}

export function parseMoney(value, options = {}) {
  if (moneyMessage(value, options)) return undefined;
  const text = normalizePaymentAmountInput(value);
  if (!text) return 0;
  return Number(text);
}

export function normalizeMpesaReceipt(value) {
  return String(value ?? '').trim().toUpperCase().replace(/\s+/g, '');
}

/** @returns {string|undefined} */
export function mpesaReceiptMessage(value) {
  const code = normalizeMpesaReceipt(value);
  if (!code) {
    return `Enter the 10-character M-Pesa code from the SMS, e.g. ${MPESA_RECEIPT_EXAMPLE}`;
  }
  if (!/^[A-Z0-9]+$/.test(code)) {
    return `Use letters and numbers only, e.g. ${MPESA_RECEIPT_EXAMPLE}`;
  }
  if (code.length !== MPESA_RECEIPT_LENGTH) {
    return `Expected 10 characters (you entered ${code.length}), e.g. ${MPESA_RECEIPT_EXAMPLE}`;
  }
  return undefined;
}

/**
 * @param {unknown} value
 * @param {{ required?: boolean }} [options]
 * @returns {string|undefined}
 */
export function emailMessage(value, options = {}) {
  const { required: isRequired = false } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    if (isRequired) return `Enter an email, e.g. ${EMAIL_EXAMPLE}`;
    return undefined;
  }
  if (!EMAIL_RE.test(text)) {
    const shown = text.length <= 40 ? text : `${text.slice(0, 37)}...`;
    return `Enter an email like ${EMAIL_EXAMPLE}. "${shown}" is not a valid email.`;
  }
  return undefined;
}

/**
 * Kenyan mobile: 07…, 7…, +254…, 254…
 * @param {unknown} value
 * @param {{ required?: boolean }} [options]
 * @returns {string|undefined}
 */
export function phoneMessage(value, options = {}) {
  const { required: isRequired = false } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    if (isRequired) return `Enter a Kenyan mobile, e.g. ${PHONE_EXAMPLE}`;
    return undefined;
  }
  const digits = text.replace(/\D/g, '');
  if (!digits) {
    return `Enter a Kenyan mobile, e.g. ${PHONE_EXAMPLE}. Letters are not allowed.`;
  }
  const ok =
    (digits.startsWith('254') && digits.length === 12) ||
    (digits.startsWith('0') && digits.length === 10) ||
    (digits.length === 9 && (digits[0] === '1' || digits[0] === '7'));
  if (!ok) {
    return `Enter a Kenyan mobile, e.g. ${PHONE_EXAMPLE}. You entered ${digits.length} digits.`;
  }
  return undefined;
}

/**
 * @param {unknown} value
 * @param {{ label?: string, example?: string, min?: number, required?: boolean }} [options]
 * @returns {string|undefined}
 */
export function personNameMessage(value, options = {}) {
  const {
    label = 'name',
    example = NAME_EXAMPLE,
    min = 2,
    required: isRequired = true,
  } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    if (!isRequired) return undefined;
    return `Enter ${label}, e.g. ${example}`;
  }
  if (text.length < min) {
    const titled = label.charAt(0).toUpperCase() + label.slice(1);
    return `${titled} must be at least ${min} characters, e.g. ${example}`;
  }
  return undefined;
}

/**
 * @param {unknown} value
 * @param {{ required?: boolean, label?: string }} [options]
 * @returns {string|undefined}
 */
export function dateMessage(value, options = {}) {
  const { required: isRequired = true, label = 'date' } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    if (!isRequired) return undefined;
    return `Enter a ${label}, e.g. ${DATE_EXAMPLE}`;
  }
  if (!ISO_DATE_RE.test(text)) {
    return `Use YYYY-MM-DD, e.g. ${DATE_EXAMPLE}`;
  }
  const [year, month, day] = text.split('-').map(Number);
  const dt = new Date(Date.UTC(year, month - 1, day));
  if (
    dt.getUTCFullYear() !== year ||
    dt.getUTCMonth() !== month - 1 ||
    dt.getUTCDate() !== day
  ) {
    return `Use a real calendar date, e.g. ${DATE_EXAMPLE}`;
  }
  return undefined;
}

/**
 * @param {unknown} value
 * @param {{ required?: boolean, min?: number, label?: string, example?: string }} [options]
 * @returns {string|undefined}
 */
export function integerMessage(value, options = {}) {
  const {
    required: isRequired = false,
    min = 0,
    label = 'whole number',
    example = QUANTITY_EXAMPLE,
  } = options;
  const text = String(value ?? '').trim();
  if (!text) {
    if (!isRequired) return undefined;
    return `Enter a ${label}, e.g. ${example}`;
  }
  if (!INT_RE.test(text)) {
    return `Use a whole number (no decimals), e.g. ${example}`;
  }
  const number = Number(text);
  if (number < min) {
    const titled = label.charAt(0).toUpperCase() + label.slice(1);
    return `${titled} must be at least ${min}, e.g. ${example}`;
  }
  return undefined;
}

/** @returns {string|undefined} */
export function requiredChoiceMessage(value, label = 'option') {
  if (value === null || value === undefined) return `Select a ${label}`;
  if (typeof value === 'string' && !value.trim()) return `Select a ${label}`;
  return undefined;
}
