/**
 * Shared test helpers for React unit tests.
 */
import { render } from '@testing-library/react';

export function createLocalStorageMock() {
  let store = {};
  return {
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, value) => {
      store[key] = String(value);
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
}

export function installLocalStorageMock() {
  const mock = createLocalStorageMock();
  Object.defineProperty(window, 'localStorage', { value: mock, writable: true });
  return mock;
}

export function installSessionStorageMock() {
  const mock = createLocalStorageMock();
  Object.defineProperty(window, 'sessionStorage', { value: mock, writable: true });
  return mock;
}

/** Minimal render without router — extend when component tests need providers. */
export function renderPlain(ui, options) {
  return render(ui, options);
}
