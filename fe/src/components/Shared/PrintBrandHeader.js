import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  DEFAULT_CONTACT_PHONE,
  DEFAULT_STORE_TAGLINE,
  resolveStoreLogoUrl,
  resolveStoreName,
} from '../../utils/storeBranding';
import StoreLogo from './StoreLogo';

/** Store logo, name and contact shown only on printed pages. */
export default function PrintBrandHeader({ title }) {
  const { settings } = useStoreSettings();
  const storeName = resolveStoreName(settings);
  return (
    <div className="hidden print:flex flex-col items-center text-center" data-testid="print-brand-header">
      <StoreLogo
        src={resolveStoreLogoUrl(settings)}
        alt={storeName}
        className="mb-1 h-16 w-16 object-contain"
      />
      <p className="text-base font-semibold">{storeName}</p>
      <p className="text-xs">{DEFAULT_STORE_TAGLINE} · Tel: {DEFAULT_CONTACT_PHONE}</p>
      {title ? <p className="mt-1 text-sm font-medium">{title}</p> : null}
    </div>
  );
}
