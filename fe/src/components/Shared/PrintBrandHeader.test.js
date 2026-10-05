import { render, screen } from '@testing-library/react';

import PrintBrandHeader from './PrintBrandHeader';
import { cacheStoreSettings } from '../../utils/storeSettingsCache';
import { DEFAULT_BRAND_LOGO } from '../../utils/storeBranding';

jest.mock('../../services/api', () => ({
  storeSettingsAPI: { get: jest.fn() },
}));

describe('PrintBrandHeader', () => {
  afterEach(() => localStorage.clear());

  it('prints the uploaded store logo, name and document title', () => {
    cacheStoreSettings({ store_name: 'Omuwenga Furniture', receipt_logo_url: '/media/receipt/brand.png' });
    render(<PrintBrandHeader title="Sales by person" />);
    expect(screen.getByAltText('Omuwenga Furniture')).toHaveAttribute('src', '/media/receipt/brand.png');
    expect(screen.getByText('Sales by person')).toBeInTheDocument();
  });

  it('falls back to the packaged logo when nothing is uploaded', () => {
    render(<PrintBrandHeader />);
    expect(screen.getByAltText('Omuwenga Suppliers')).toHaveAttribute('src', DEFAULT_BRAND_LOGO);
  });
});
