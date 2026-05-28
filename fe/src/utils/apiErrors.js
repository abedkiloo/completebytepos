/**
 * Turn DRF / Django error payloads into a single string for toasts.
 */
export function formatApiError(error, fallback = 'Something went wrong') {
  const data = error?.response?.data;
  if (!data) {
    return error?.message || fallback;
  }
  if (typeof data === 'string') {
    return data;
  }
  if (data.error) {
    if (typeof data.error === 'string') {
      return data.error;
    }
    if (Array.isArray(data.error)) {
      return data.error.join('; ');
    }
  }
  if (data.detail) {
    return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
  }
  if (Array.isArray(data)) {
    return data.join('; ');
  }
  if (typeof data === 'object') {
    const parts = [];
    Object.values(data).forEach((val) => {
      if (Array.isArray(val)) {
        parts.push(...val.map(String));
      } else if (val != null) {
        parts.push(String(val));
      }
    });
    if (parts.length) {
      return parts.join('; ');
    }
  }
  return fallback;
}
