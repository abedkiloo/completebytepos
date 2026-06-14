import React from 'react';
import { render } from '@testing-library/react';
import SessionIdleGuard from './SessionIdleGuard';
import * as sessionIdle from '../../utils/sessionIdle';

jest.mock('../../utils/sessionIdle', () => ({
  startIdleSessionWatch: jest.fn(),
  stopIdleSessionWatch: jest.fn(),
}));

describe('SessionIdleGuard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('starts idle watch on mount and stops on unmount', () => {
    const { unmount } = render(<SessionIdleGuard />);
    expect(sessionIdle.startIdleSessionWatch).toHaveBeenCalledTimes(1);
    unmount();
    expect(sessionIdle.stopIdleSessionWatch).toHaveBeenCalledTimes(1);
  });
});
