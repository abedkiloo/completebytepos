import { resolveMediaUrl } from './mediaUrl';

describe('resolveMediaUrl', () => {
  const originalLocation = window.location;

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
  });

  test('rewrites backend hostname to same-origin media path', () => {
    Object.defineProperty(window, 'location', {
      value: { hostname: '193.37.213.177', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://backend:8000/media/products/x.jpg')
    ).toBe('/media/products/x.jpg');
  });

  test('keeps relative media paths', () => {
    expect(resolveMediaUrl('/media/x.jpg')).toBe('/media/x.jpg');
  });

  test('returns invalid urls unchanged', () => {
    expect(resolveMediaUrl('not-a-url')).toBe('not-a-url');
    expect(resolveMediaUrl('')).toBe('');
  });

  test('maps port 8000 media to same-origin path in production', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    Object.defineProperty(window, 'location', {
      value: { hostname: '193.37.213.177', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://193.37.213.177:8000/media/products/x.jpg')
    ).toBe('/media/products/x.jpg');
    process.env.NODE_ENV = prev;
  });

  test('rewrites dev :3000 media base to same-origin path', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    Object.defineProperty(window, 'location', {
      value: { hostname: 'localhost', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://localhost:3000/media/products/x.jpg')
    ).toBe('/media/products/x.jpg');
    process.env.NODE_ENV = prev;
  });

  test('leaves non-media absolute URLs unchanged', () => {
    expect(resolveMediaUrl('https://cdn.example.com/logo.png')).toBe(
      'https://cdn.example.com/logo.png'
    );
  });

  test('rewrites dev media without standard ports to same-origin path', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    Object.defineProperty(window, 'location', {
      value: { hostname: 'localhost', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://shop.example.com/media/products/x.jpg')
    ).toBe('/media/products/x.jpg');
    process.env.NODE_ENV = prev;
  });

  test('aligns localhost vs 127.0.0.1 for direct :8000 in dev', () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';
    Object.defineProperty(window, 'location', {
      value: { hostname: 'localhost', port: '3000', protocol: 'http:' },
      writable: true,
    });
    expect(
      resolveMediaUrl('http://127.0.0.1:8000/media/products/x.jpg')
    ).toBe('http://localhost:8000/media/products/x.jpg');
    process.env.NODE_ENV = prev;
  });
});
