const { createProxyMiddleware } = require('http-proxy-middleware');

/**
 * CRA dev server: proxy /media to Django so same-origin image URLs work.
 * In Docker dev, set REACT_APP_PROXY_TARGET=http://backend:8000
 */
module.exports = function setupMediaProxy(app) {
  const fromApi = (process.env.REACT_APP_API_URL || '')
    .trim()
    .replace(/\/api\/?$/i, '');
  const target =
    (process.env.REACT_APP_PROXY_TARGET || '').trim() ||
    fromApi ||
    'http://localhost:8000';

  app.use(
    '/media',
    createProxyMiddleware({
      target,
      changeOrigin: true,
    })
  );
};
