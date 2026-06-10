import { renderHook, act } from '@testing-library/react';
import { useDebouncedValue } from './useDebouncedValue';

jest.useFakeTimers();

describe('useDebouncedValue', () => {
  test('updates after delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebouncedValue(value, delay),
      { initialProps: { value: 'a', delay: 300 } }
    );

    expect(result.current).toBe('a');
    rerender({ value: 'ab', delay: 300 });
    expect(result.current).toBe('a');

    act(() => {
      jest.advanceTimersByTime(299);
    });
    expect(result.current).toBe('a');

    act(() => {
      jest.advanceTimersByTime(1);
    });
    expect(result.current).toBe('ab');
  });
});
