import { render } from '@testing-library/react';
import BrandMark from './BrandMark';
import { DEFAULT_BRAND_LOGO } from '../../utils/storeBranding';

describe('BrandMark', () => {
  it('renders the packaged plate logo with the store name as alt text', () => {
    const { container } = render(<BrandMark name="Omuwenga Suppliers" />);
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', DEFAULT_BRAND_LOGO);
    expect(img).toHaveAttribute('alt', 'Omuwenga Suppliers');
  });

  it('allows an empty alt when the name is already shown beside it', () => {
    const { container } = render(<BrandMark alt="" />);
    expect(container.querySelector('img')).toHaveAttribute('alt', '');
  });
});
