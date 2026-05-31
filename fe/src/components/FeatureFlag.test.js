import React from 'react';
import { render, screen } from '@testing-library/react';
import FeatureFlag from './FeatureFlag';

jest.mock('../hooks/useModuleSettings', () => ({
  useModuleSettings: jest.fn(),
}));

const { useModuleSettings } = require('../hooks/useModuleSettings');

describe('FeatureFlag', () => {
  test('renders children when flag is on', () => {
    useModuleSettings.mockReturnValue({ settings: { show_status: true } });
    render(
      <FeatureFlag module="products" flag="show_status">
        <span>Visible</span>
      </FeatureFlag>
    );
    expect(screen.getByText('Visible')).toBeInTheDocument();
  });

  test('renders nothing when flag is off', () => {
    useModuleSettings.mockReturnValue({ settings: { show_status: false } });
    render(
      <FeatureFlag module="products" flag="show_status">
        <span>Hidden</span>
      </FeatureFlag>
    );
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });
});
