import { toast } from './toast';

/**
 * Build a single top-of-form message from field/API error maps.
 * Prefers `_form`. For field-only errors, returns a summary so field messages
 * are not duplicated in the banner.
 */
export function formBannerMessage(errors, fallback = 'Please fix the highlighted fields below.') {
  if (!errors || typeof errors !== 'object') return null;
  const keys = Object.keys(errors);
  if (!keys.length) return null;
  if (typeof errors._form === 'string' && errors._form.trim()) {
    return errors._form.trim();
  }
  const hasFieldError = keys.some((key) => {
    if (key === '_form') return false;
    const val = errors[key];
    return Boolean(typeof val === 'string' ? val.trim() : val);
  });
  return hasFieldError ? fallback : null;
}

/**
 * Show toast + optional form banner so non-tech users see the error in-page.
 * @returns {string} the message shown
 */
export function reportFormError(setBanner, message, duration) {
  const msg = String(message || 'Something went wrong').trim() || 'Something went wrong';
  if (typeof setBanner === 'function') {
    setBanner({ type: 'error', message: msg });
  }
  if (duration !== undefined) toast.error(msg, duration);
  else toast.error(msg);
  return msg;
}

export function reportFormWarning(setBanner, message, duration) {
  const msg = String(message || '').trim();
  if (!msg) return '';
  if (typeof setBanner === 'function') {
    setBanner({ type: 'warning', message: msg });
  }
  if (duration !== undefined) toast.warning(msg, duration);
  else toast.warning(msg);
  return msg;
}

export function clearFormBanner(setBanner) {
  if (typeof setBanner === 'function') setBanner(null);
}
