import { DEFAULT_BRAND_LOGO } from '../../utils/storeBranding';

/** Uploaded store logo that falls back to the packaged mark if it cannot load. */
export default function StoreLogo({ src, alt = '', className = '' }) {
  return (
    <img
      src={src || DEFAULT_BRAND_LOGO}
      alt={alt}
      className={className}
      onError={(event) => {
        const img = event.currentTarget;
        if (img.dataset.fallback) return;
        img.dataset.fallback = '1';
        img.src = DEFAULT_BRAND_LOGO;
      }}
    />
  );
}
