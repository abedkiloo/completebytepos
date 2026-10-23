const ORIGINAL_ENV = process.env;

describe('resolveApiBaseUrl', () => {
  beforeEach(() => {
    jest.resetModules();
    process.env = { ...ORIGINAL_ENV };
  });

  afterAll(() => {
    process.env = ORIGINAL_ENV;
  });

  it('uses explicit URL when set', () => {
    process.env.REACT_APP_API_URL = 'http://example.com:8000/api';
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('http://example.com:8000/api');
  });

  it('rewrites /api to host :8000 when not a production build', () => {
    process.env.NODE_ENV = 'development';
    process.env.REACT_APP_API_URL = '/api';
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { protocol: 'http:', hostname: '193.37.213.177', port: '3000' },
    });
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('http://193.37.213.177:8000/api');
  });

  it('keeps /api in production builds', () => {
    process.env.NODE_ENV = 'production';
    process.env.REACT_APP_API_URL = '/api';
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('/api');
  });

  it('rewrites a baked public :8000 URL to /api on the nginx SPA', () => {
    process.env.NODE_ENV = 'production';
    process.env.REACT_APP_API_URL = 'http://193.37.213.177:8000/api';
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        protocol: 'http:',
        hostname: '193.37.213.177',
        port: '3000',
        origin: 'http://193.37.213.177:3000',
      },
    });
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('/api');
  });

  it('defaults to localhost when unset', () => {
    delete process.env.REACT_APP_API_URL;
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('http://localhost:8000/api');
  });

  it('keeps a non-localhost baked URL on the nginx SPA', () => {
    process.env.NODE_ENV = 'production';
    process.env.REACT_APP_API_URL = 'https://api.example.com/api';
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        protocol: 'https:',
        hostname: '193.37.213.177',
        port: '3000',
        origin: 'https://193.37.213.177:3000',
      },
    });
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('https://api.example.com/api');
  });

  it('falls back to /api when the baked URL cannot be parsed on the nginx SPA', () => {
    process.env.NODE_ENV = 'production';
    process.env.REACT_APP_API_URL = 'http://%';
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        protocol: 'http:',
        hostname: '193.37.213.177',
        port: '80',
        origin: 'http://193.37.213.177',
      },
    });
    const { resolveApiBaseUrl } = require('./apiBaseUrl');
    expect(resolveApiBaseUrl()).toBe('/api');
  });
});
