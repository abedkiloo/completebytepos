import { formatApiError } from './apiErrors';

describe('formatApiError', () => {
  it('returns message when no response', () => {
    expect(formatApiError(new Error('network'))).toBe('network');
    expect(formatApiError({}, 'fallback')).toBe('fallback');
  });

  it('handles string and detail payloads', () => {
    expect(formatApiError({ response: { data: 'Denied' } })).toBe('Denied');
    expect(formatApiError({ response: { data: { detail: 'Not found' } } })).toBe('Not found');
  });

  it('handles error field as string or array', () => {
    expect(formatApiError({ response: { data: { error: 'Bad' } } })).toBe('Bad');
    expect(formatApiError({ response: { data: { error: ['a', 'b'] } } })).toBe('a; b');
  });

  it('flattens field validation arrays', () => {
    expect(
      formatApiError({
        response: { data: { name: ['Required'], sku: 'Taken' } },
      })
    ).toBe('Required; Taken');
  });

  it('handles top-level array payloads', () => {
    expect(formatApiError({ response: { data: ['a', 'b'] } })).toBe('a; b');
  });

  it('handles non-string detail objects', () => {
    expect(formatApiError({ response: { data: { detail: { code: 1 } } } })).toContain('code');
  });

  it('returns fallback for empty object payload', () => {
  expect(formatApiError({ response: { data: {} } }, 'fallback')).toBe('fallback');
  expect(
    formatApiError({ response: { status: 500, data: '<html>traceback</html>' } }, 'Could not save')
  ).toBe('Could not save (500)');
  expect(
    formatApiError({ response: { status: 403, data: {} } }, 'Could not save this call.')
  ).toBe('Could not save this call. (403)');
});
});
