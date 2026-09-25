import { DEFAULT_BRAND_LOGO, DEFAULT_STORE_NAME } from '../../utils/storeBranding';

/** Packaged Omuwenga plate mark used in the app chrome. */
export default function BrandMark({
  className = 'h-9 w-9',
  alt,
  name = DEFAULT_STORE_NAME,
}) {
  return (
    <img
      src={DEFAULT_BRAND_LOGO}
      alt={alt === undefined ? name : alt}
      className={`shrink-0 object-contain ${className}`}
    />
  );
}
