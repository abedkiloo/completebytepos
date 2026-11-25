/**
 * Turn DRF / Django error payloads into a single string for toasts.
 *
 * Prefers ``error``, then ``detail``. HTML bodies and empty strings fall back
 * so call-book and money screens never show a blank toast.
 *
 * @param {unknown} error Axios-like error or Error.
 * @param {string} [fallback='Something went wrong'] Used when nothing useful is found.
 * @returns {string} Short people-facing message.
 */
export function formatApiError(error, fallback = 'Something went wrong') {
  const data = error?.response?.data;
  if (!data) {
    const network = String(error?.message || '').trim();
    if (network && network !== 'Error') return network;
    const status = error?.response?.status;
    if (status) return `${fallback} (${status})`;
    return fallback;
  }
  if (typeof data === 'string') {
    const text = data.trim();
    if (!text) return fallback;
    if (text.includes('<') || text.toLowerCase().includes('traceback')) {
      const status = error?.response?.status;
      return status ? `${fallback} (${status})` : fallback;
    }
    return text.length > 300 ? `${text.slice(0, 300)}…` : text;
  }
  if (data.error) {
    if (typeof data.error === 'string' && data.error.trim()) {
      return data.error.trim();
    }
    if (Array.isArray(data.error)) {
      const joined = data.error.map(String).filter(Boolean).join('; ');
      if (joined) return joined;
    }
  }
  if (data.detail) {
    if (typeof data.detail === 'string' && data.detail.trim()) {
      return data.detail.trim();
    }
    if (Array.isArray(data.detail)) {
      const joined = data.detail.map(String).filter(Boolean).join('; ');
      if (joined) return joined;
    }
    try {
      return JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
  }
  if (Array.isArray(data)) {
    const joined = data.map(String).filter(Boolean).join('; ');
    if (joined) return joined;
  }
  if (typeof data === 'object') {
    const parts = [];
    Object.values(data).forEach((val) => {
      if (Array.isArray(val)) {
        parts.push(...val.map(String));
      } else if (val != null && val !== '') {
        parts.push(String(val));
      }
    });
    if (parts.length) {
      return parts.join('; ');
    }
  }
  const status = error?.response?.status;
  return status ? `${fallback} (${status})` : fallback;
}
