import { Monitor, Smartphone } from 'lucide-react';

const CHANNEL_LABELS = {
  web: 'Web',
  mobile: 'Mobile app',
};

export function saleChannelLabel(channel) {
  return CHANNEL_LABELS[channel] || '';
}

/**
 * Standard device icons: Lucide Monitor (desktop/web) and Smartphone (app).
 * Hidden when the origin was not recorded (legacy sales).
 */
export default function SaleChannelIcon({ channel, className = 'h-3.5 w-3.5' }) {
  const label = saleChannelLabel(channel);
  if (channel === 'mobile') {
    return (
      <Smartphone
        className={`${className} shrink-0 text-muted-foreground`}
        aria-label={label}
        title={label}
      />
    );
  }
  if (channel === 'web') {
    return (
      <Monitor
        className={`${className} shrink-0 text-muted-foreground`}
        aria-label={label}
        title={label}
      />
    );
  }
  return null;
}

export function SaleNumberWithChannel({ saleNumber, channel, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 min-w-0 ${className}`.trim()}>
      <SaleChannelIcon channel={channel} />
      <span className="truncate">{saleNumber}</span>
    </span>
  );
}
