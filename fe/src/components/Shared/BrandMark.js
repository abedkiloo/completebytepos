import { DEFAULT_BRAND_LOGO, DEFAULT_STORE_NAME } from '../../utils/storeBranding';
import StoreLogo from './StoreLogo';

/** Omuwenga plate mark; pass `src` to show the uploaded store logo instead. */
export default function BrandMark({
  className = 'h-9 w-9',
  alt,
  name = DEFAULT_STORE_NAME,
  src = DEFAULT_BRAND_LOGO,
}) {
  return (
    <StoreLogo
      src={src}
      alt={alt === undefined ? name : alt}
      className={`shrink-0 object-contain ${className}`}
    />
  );
}
