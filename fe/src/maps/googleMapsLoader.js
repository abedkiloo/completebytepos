import { mapsJsKey } from './mapsConfig';

export function loadGoogleMapsJs(
  key = mapsJsKey(),
  { documentRef = document, windowRef = window } = {},
) {
  if (!key) {
    return Promise.reject(new Error('Maps JS key is not configured'));
  }
  if (windowRef.google && windowRef.google.maps) {
    return Promise.resolve(windowRef.google);
  }
  if (windowRef.__omuwengaMapsLoader) {
    return windowRef.__omuwengaMapsLoader;
  }
  windowRef.__omuwengaMapsLoader = new Promise((resolve, reject) => {
    const script = documentRef.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}`;
    script.async = true;
    if (!script.dataset) script.dataset = {};
    script.dataset.testid = 'google-maps-js';
    script.onload = () => {
      if (windowRef.google && windowRef.google.maps) {
        resolve(windowRef.google);
      } else {
        reject(new Error('Google Maps loaded without maps namespace'));
      }
    };
    script.onerror = () => reject(new Error('Failed to load Google Maps'));
    (documentRef.head || documentRef.body).appendChild(script);
  });
  return windowRef.__omuwengaMapsLoader;
}

export function resetGoogleMapsLoader(windowRef = window) {
  delete windowRef.__omuwengaMapsLoader;
}
