import { configuredMapsKey, localISODate, mapsJsKey } from './mapsConfig';
import { geometryFromStops, pinsFromGeometry } from './routeGeometry';

describe('mapsConfig', () => {
  const original = process.env.REACT_APP_GOOGLE_MAPS_KEY;

  afterEach(() => {
    process.env.REACT_APP_GOOGLE_MAPS_KEY = original;
  });

  test('rejects placeholders and reads env', () => {
    expect(configuredMapsKey('')).toBe('');
    expect(configuredMapsKey('REPLACE_WITH_MAPS_JS_API_KEY')).toBe('');
    expect(configuredMapsKey('AIzaSyReal')).toBe('AIzaSyReal');
    process.env.REACT_APP_GOOGLE_MAPS_KEY = 'REPLACE_WITH_MAPS_JS_API_KEY';
    expect(mapsJsKey()).toBe('');
    process.env.REACT_APP_GOOGLE_MAPS_KEY = 'AIzaSyWeb';
    expect(mapsJsKey()).toBe('AIzaSyWeb');
  });

  test('localISODate is calendar-local', () => {
    expect(localISODate(new Date(2026, 8, 24, 22, 0, 0))).toBe('2026-09-24');
  });
});

describe('routeGeometry', () => {
  test('builds pins and skips stops without coordinates', () => {
    const geo = geometryFromStops([
      { id: 1, sequence: 1, label: 'A', latitude: -1.3, longitude: 36.8 },
      { id: 2, sequence: 2, label: 'B' },
    ]);
    expect(geo.path).toHaveLength(2);
    expect(geo.stops[1].latitude).toBeNull();
    const pins = pinsFromGeometry(geo);
    expect(pins[0].isDepot).toBe(true);
    expect(pins).toHaveLength(2);
  });

  test('reads nested site coordinates', () => {
    const geo = geometryFromStops([
      { id: 9, site: { latitude: '-1.2', longitude: '36.9' }, customer_name: 'Ada' },
    ]);
    expect(geo.stops[0].label).toBe('Ada');
    expect(geo.stops[0].latitude).toBe(-1.2);
  });
});
