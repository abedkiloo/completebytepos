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
});
