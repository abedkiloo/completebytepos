import React from 'react';
import { ExternalLink } from 'lucide-react';

import { resolveMediaUrl } from '../../utils/mediaUrl';

/**
 * Thumbnail + open-full link for debt/sale payment screenshots.
 *
 * @param {object} props
 * @param {string|null|undefined} props.url Raw or absolute media URL from the API.
 * @param {string} [props.label='Receipt'] Accessible label / link text.
 * @param {string} [props.className]
 * @param {'compact'|'card'} [props.variant='compact'] Compact for tables; card for detail panels.
 */
export default function ReceiptImageLink({
  url,
  label = 'Receipt',
  className = '',
  variant = 'compact',
}) {
  const src = resolveMediaUrl(String(url || '').trim());
  if (!src) return null;

  if (variant === 'card') {
    return (
      <a
        href={src}
        target="_blank"
        rel="noreferrer"
        className={`block max-w-full ${className}`.trim()}
        data-testid="receipt-image-link"
        title="Open full image"
      >
        <img
          src={src}
          alt={label}
          data-testid="receipt-image-thumb"
          className="mt-1 max-h-48 w-full rounded-md border object-contain bg-background"
        />
        <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-primary">
          Open full image
          <ExternalLink className="h-3 w-3" aria-hidden />
        </span>
      </a>
    );
  }

  return (
    <a
      href={src}
      target="_blank"
      rel="noreferrer"
      className={`mt-1 inline-flex items-center gap-1.5 text-xs text-primary hover:underline ${className}`.trim()}
      data-testid="receipt-image-link"
      title="Open full image"
    >
      <img
        src={src}
        alt=""
        data-testid="receipt-image-thumb"
        className="h-10 w-10 rounded border object-cover bg-background"
      />
      <span className="inline-flex items-center gap-1">
        {label}
        <ExternalLink className="h-3 w-3" aria-hidden />
      </span>
    </a>
  );
}
