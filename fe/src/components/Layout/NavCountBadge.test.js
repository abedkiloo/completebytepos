import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('../../services/api', () => ({}));

import NavCountBadge from './NavCountBadge';

describe('NavCountBadge', () => {
  test('renders nothing for zero count', () => {
    const { container } = render(<NavCountBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('renders count pill', () => {
    render(<NavCountBadge count={5} labelPrefix="tasks" />);
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByLabelText('5 tasks')).toBeInTheDocument();
  });

  test('caps large counts at 99+', () => {
    render(<NavCountBadge count={150} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });
});
