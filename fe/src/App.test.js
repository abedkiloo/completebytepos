import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('./services/api', () => ({
  authAPI: { me: jest.fn().mockRejectedValue(new Error('not authenticated')) },
}));

jest.mock('./components/Installation/SetupGate', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="setup-gate">{children}</div>,
}));

jest.mock('./components/Layout/AppLayout', () => ({
  __esModule: true,
  default: () => <div data-testid="app-layout">App layout</div>,
}));

jest.mock('./components/Toast/ToastContainer', () => ({
  __esModule: true,
  default: () => null,
}));

import App from './App';

test('renders app shell without crashing', () => {
  render(<App />);
  expect(screen.getByTestId('router')).toBeInTheDocument();
  expect(screen.getByTestId('setup-gate')).toBeInTheDocument();
});
