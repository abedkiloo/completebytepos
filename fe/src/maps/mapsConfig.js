/** Browser Maps JS key. Server Routes key never belongs here. */

const PLACEHOLDERS = ['REPLACE_WITH', 'YOUR_KEY', 'YOUR-KEY', 'CHANGE-ME', 'CHANGEME', 'CHANGE_ME'];

export function configuredMapsKey(raw) {
  const key = (raw || '').trim();
  if (!key) return '';
  const upper = key.toUpperCase().replace(/\s/g, '');
  if (PLACEHOLDERS.some((marker) => upper.includes(marker))) return '';
  return key;
}

export function mapsJsKey() {
  return configuredMapsKey(process.env.REACT_APP_GOOGLE_MAPS_KEY);
}

export function localISODate(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
