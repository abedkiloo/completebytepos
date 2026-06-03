/**
 * Make product image URLs load in the browser (dev CRA, docker nginx, VPS).
 */
export function resolveMediaUrl(url) {
  if (!url || typeof url !== 'string') return url;

  const trimmed = url.trim();
  if (!trimmed) return url;

  if (trimmed.startsWith('/')) {
    if (typeof window === 'undefined') return trimmed;
    if (process.env.NODE_ENV !== 'production') {
      const { protocol, hostname } = window.location;
      return `${protocol}//${hostname}:8000${trimmed}`;
    }
    return trimmed;
  }

  if (typeof window === 'undefined') return trimmed;

  try {
    const parsed = new URL(trimmed);
    const pagePort = window.location.port;
    const pageHost = window.location.hostname;

    if (parsed.hostname === 'backend') {
      parsed.hostname = pageHost;
      parsed.port = pagePort || '';
    }

    // Production: prefer nginx on :3000 (proxies /media/) over direct :8000
    if (
      process.env.NODE_ENV === 'production' &&
      pagePort === '3000' &&
      parsed.port === '8000' &&
      parsed.pathname.startsWith('/media/')
    ) {
      parsed.port = '3000';
    }

    return parsed.toString();
  } catch {
    return trimmed;
  }
}
