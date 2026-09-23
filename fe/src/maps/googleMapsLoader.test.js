import { loadGoogleMapsJs, resetGoogleMapsLoader } from './googleMapsLoader';

function fakeDocument() {
  const created = [];
  const parent = {
    appendChild(el) {
      created.push(el);
      return el;
    },
  };
  return {
    created,
    createElement() {
      return {
        src: '',
        async: false,
        dataset: {},
        onload: null,
        onerror: null,
      };
    },
    head: parent,
    body: parent,
  };
}

describe('googleMapsLoader', () => {
  const windowRef = {};

  afterEach(() => {
    resetGoogleMapsLoader(windowRef);
    delete windowRef.google;
  });

  test('rejects missing key', async () => {
    await expect(loadGoogleMapsJs('', { windowRef, documentRef: fakeDocument() })).rejects.toThrow(
      'not configured',
    );
  });

  test('resolves when google.maps already exists', async () => {
    windowRef.google = { maps: { Map: function Map() {} } };
    await expect(loadGoogleMapsJs('AIza', { windowRef, documentRef: fakeDocument() })).resolves.toBe(
      windowRef.google,
    );
  });

  test('reuses in-flight loader and loads script', async () => {
    const documentRef = fakeDocument();
    const p1 = loadGoogleMapsJs('AIza', { windowRef, documentRef });
    const p2 = loadGoogleMapsJs('AIza', { windowRef, documentRef });
    expect(p1).toBe(p2);
    expect(documentRef.created[0].src).toContain('key=AIza');
    windowRef.google = { maps: {} };
    documentRef.created[0].onload();
    await expect(p1).resolves.toBe(windowRef.google);
  });

  test('fails when script errors or maps namespace is missing', async () => {
    const documentRef = fakeDocument();
    const failed = loadGoogleMapsJs('AIzaFail', { windowRef, documentRef });
    documentRef.created[0].onerror();
    await expect(failed).rejects.toThrow('Failed to load');

    resetGoogleMapsLoader(windowRef);
    const missingDoc = fakeDocument();
    const missing = loadGoogleMapsJs('AIzaMissing', { windowRef, documentRef: missingDoc });
    missingDoc.created[0].onload();
    await expect(missing).rejects.toThrow('without maps namespace');
  });
});
