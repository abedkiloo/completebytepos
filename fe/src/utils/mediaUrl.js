/**
 * Make product image URLs load in the browser (dev CRA + proxy, docker nginx, VPS).
 */
export function resolveMediaUrl(url) {
  if (!url || typeof url !== 'string') return url;

  const trimmed = url.trim();
  if (!trimmed) return url;

  if (trimmed.startsWith('/')) {
    return trimmed;
  }

  if (typeof window === 'undefined') return trimmed;

  try {
    const parsed = new URL(trimmed);
    const pageHost = window.location.hostname;
    const isProd = process.env.NODE_ENV === 'production';

    if (!parsed.pathname.startsWith('/media/')) {
      return trimmed;
    }

    // Docker-internal hostnames are not reachable from the browser.
    if (parsed.hostname === 'backend' || parsed.hostname === 'frontend') {
      return parsed.pathname + (parsed.search || '');
    }

    // Same-origin /media (nginx in prod, setupProxy.js in dev).
    if (isProd) {
      return parsed.pathname + (parsed.search || '');
    }

    // Dev: MEDIA_PUBLIC_BASE_URL may point at :3000 without a working /media route.
    if (parsed.port === '3000') {
      return parsed.pathname + (parsed.search || '');
    }

    // Dev without proxy: keep direct :8000, align localhost vs 127.0.0.1 with the page.
    if (parsed.port === '8000') {
      if (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost') {
        parsed.hostname = pageHost;
      }
      return parsed.toString();
    }

    return parsed.pathname + (parsed.search || '');
  } catch {
    return trimmed;
  }
}
