import React from 'react';
import { buildVariantDraftSummary } from '../../utils/variantDraftSummary';

export default function VariantDraftSummary({
  productName,
  draftsByKey,
  sizes = [],
  colors = [],
  compact = false,
  className = '',
}) {
  const { lines, totalStock, count } = buildVariantDraftSummary(draftsByKey, {
    sizes,
    colors,
  });

  if (!count) return null;

  const heading = productName?.trim()
    ? `${productName.trim()} — ${count} variant${count === 1 ? '' : 's'} configured`
    : `${count} variant${count === 1 ? '' : 's'} configured`;

  if (compact) {
    return (
      <div className={`text-sm text-muted-foreground ${className}`}>
        <span className="font-medium text-foreground">{heading}</span>
        {' — '}
        {lines.map((line) => line.label).join(', ')}
      </div>
    );
  }

  return (
    <div
      className={`rounded-md border border-border/80 bg-muted/30 p-3 text-sm ${className}`}
      data-testid="variant-draft-summary"
    >
      <p className="font-medium text-foreground">
        {productName?.trim()
          ? `Adding “${productName.trim()}” with variants:`
          : 'Variant setup summary:'}
      </p>
      <ul className="mt-2 space-y-1">
        {lines.map((line) => (
          <li key={line.key} className="text-foreground">
            <span className="font-medium">{line.label}</span>
            {line.details.length ? (
              <span className="text-muted-foreground"> — {line.details.join(', ')}</span>
            ) : null}
          </li>
        ))}
      </ul>
      {lines.some((line) => line.draft.stock_quantity !== '' && line.draft.stock_quantity != null) ? (
        <p className="mt-2 text-muted-foreground">
          Total variant stock: <span className="font-medium text-foreground">{totalStock}</span>
        </p>
      ) : null}
      <p className="mt-2 text-xs text-muted-foreground">
        Review this list before saving. Values are kept when you add more sizes or colors.
      </p>
    </div>
  );
}
