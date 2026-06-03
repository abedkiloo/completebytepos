import { resolveMediaUrl } from './mediaUrl';

describe('resolveMediaUrl', () => {
  const originalLocation = window.location;

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
  });

  test('rewrites backend hostname to page host', () => {
    Object.defineProperty(window, 'location', {
      value: { hostname: '193.37.213.177', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://backend:8000/media/products/x.jpg')
    ).toBe('http://193.37.213.177:3000/media/products/x.jpg');
  });

  test('resolves relative media path in dev', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    Object.defineProperty(window, 'location', {
      value: { hostname: 'localhost', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(resolveMediaUrl('/media/x.jpg')).toBe('http://localhost:8000/media/x.jpg');
    process.env.NODE_ENV = prev;
  });

  test('returns relative path in production', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    expect(resolveMediaUrl('/media/x.jpg')).toBe('/media/x.jpg');
    process.env.NODE_ENV = prev;
  });

  test('returns invalid urls unchanged', () => {
    expect(resolveMediaUrl('not-a-url')).toBe('not-a-url');
    expect(resolveMediaUrl('')).toBe('');
  });

  test('maps port 8000 media to 3000 in production', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    Object.defineProperty(window, 'location', {
      value: { hostname: '193.37.213.177', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://193.37.213.177:8000/media/products/x.jpg')
    ).toBe('http://193.37.213.177:3000/media/products/x.jpg');
    process.env.NODE_ENV = prev;
  });
});
