/**
 * Runtime API URL (optional). Edit on the server without rebuilding the React app.
 * Loaded before the app bundle — see public/index.html
 *
 * Production behind nginx (recommended):
 *   window.__RUNTIME_CONFIG__ = { API_URL: '/api' };
 *
 * Or absolute backend:
 *   window.__RUNTIME_CONFIG__ = { API_URL: 'http://YOUR_SERVER_IP:8000/api' };
 */
window.__RUNTIME_CONFIG__ = window.__RUNTIME_CONFIG__ || {
  API_URL: '',
};
