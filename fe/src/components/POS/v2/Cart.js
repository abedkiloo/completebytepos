import React from 'react';
import { Trash2, Plus, Minus, ShoppingCart, AlertTriangle } from 'lucide-react';

import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { formatCurrency } from '../../../utils/formatters';
import { cn } from '../../../lib/cn';
import { getLineStockCap } from './usePOSState';

/**
 * Classify a cart line against its stock cap.
 *
 * Returns one of:
 *   - { kind: 'untracked' }          – item is not stock-tracked
 *   - { kind: 'over', cap, by }      – qty > cap (should not happen, but defended)
 *   - { kind: 'last', cap, atCap }   – qty within 2 of the cap
 *   - { kind: 'ok',   cap }          – plenty of stock
 */
const classifyStock = (item) => {
  const cap = getLineStockCap(item);
  if (cap === null) return { kind: 'untracked' };
  if (item.quantity > cap) return { kind: 'over', cap, by: item.quantity - cap };
  if (cap - item.quantity <= 2) return { kind: 'last', cap, atCap: item.quantity === cap };
  return { kind: 'ok', cap };
};

/**
 * Cart line list.
 *
 * Pure presentational — all mutations are owned by usePOSState and threaded
 * through callbacks. Lives inside the right-side panel beside CheckoutPanel.
 */
export function Cart({
  items,
  onAdjust,
  onRemove,
  onClear,
}) {
  if (items.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center text-muted-foreground">
        <ShoppingCart className="h-10 w-10 opacity-40" />
        <div>
          <p className="font-medium text-foreground">Cart is empty</p>
          <p className="mt-1 text-sm">Tap a product on the left to add it.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <span className="text-sm font-medium text-muted-foreground">
          {items.length} {items.length === 1 ? 'line' : 'lines'} ·{' '}
          {items.reduce((s, i) => s + i.quantity, 0)} items
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          className="h-8 text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Clear
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        <ScrollArea className="h-full">
          <ul className="divide-y">
            {items.map((item) => (
              <CartLine
                key={`${item.id}-${item.variant_id || 'base'}`}
                item={item}
                onAdjust={onAdjust}
                onRemove={onRemove}
              />
            ))}
          </ul>
        </ScrollArea>
      </div>
    </div>
  );
}

function CartLine({ item, onAdjust, onRemove }) {
  const lineTotal = item.price * item.quantity;
  const variantLabel = [item.variant?.size?.name, item.variant?.color?.name]
    .filter(Boolean)
    .join(' / ');
  const stock = classifyStock(item);
  const atCap = stock.kind === 'last' && stock.atCap;
  const over = stock.kind === 'over';

  return (
    <li
      className={cn(
        'flex items-start gap-2 px-3 py-2 transition-colors',
        over && 'bg-destructive/5'
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <span className="line-clamp-2 text-sm font-medium text-foreground">
            {item.name}
          </span>
          <button
            type="button"
            onClick={() => onRemove(item)}
            aria-label={`Remove ${item.name}`}
            className="-mr-1 -mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          {variantLabel ? (
            <>
              <span>{variantLabel}</span>
              <span>·</span>
            </>
          ) : null}
          <span>{formatCurrency(item.price)} each</span>
          <StockChip stock={stock} />
        </div>

        <div className="mt-2 flex items-center justify-between">
          <QtyStepper item={item} onAdjust={onAdjust} disablePlus={atCap || over} />
          <span className="text-sm font-semibold tabular-nums text-foreground">
            {formatCurrency(lineTotal)}
          </span>
        </div>
      </div>
    </li>
  );
}

function StockChip({ stock }) {
  if (stock.kind === 'untracked') return null;
  if (stock.kind === 'over') {
    return (
      <>
        <span>·</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-destructive/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-destructive">
          <AlertTriangle className="h-3 w-3" />
          Over by {stock.by}
        </span>
      </>
    );
  }
  if (stock.kind === 'last') {
    return (
      <>
        <span>·</span>
        <span
          className={cn(
            'rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
            stock.atCap
              ? 'bg-warning/15 text-warning'
              : 'bg-warning/10 text-warning'
          )}
        >
          {stock.atCap ? `Last ${stock.cap}` : `Only ${stock.cap} left`}
        </span>
      </>
    );
  }
  return (
    <>
      <span>·</span>
      <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
        {stock.cap} in stock
      </span>
    </>
  );
}

function QtyStepper({ item, onAdjust, disablePlus = false }) {
  return (
    <div className="inline-flex items-center rounded-md border bg-background">
      <button
        type="button"
        onClick={() => onAdjust(item, -1)}
        aria-label="Decrease quantity"
        className={cn(
          'inline-flex h-8 w-8 items-center justify-center rounded-l-md text-muted-foreground',
          'hover:bg-accent hover:text-foreground active:bg-accent/80'
        )}
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <span className="min-w-[2rem] px-2 text-center text-sm font-semibold tabular-nums">
        {item.quantity}
      </span>
      <button
        type="button"
        onClick={() => onAdjust(item, +1)}
        aria-label="Increase quantity"
        disabled={disablePlus}
        title={disablePlus ? 'No more in stock' : undefined}
        className={cn(
          'inline-flex h-8 w-8 items-center justify-center rounded-r-md text-muted-foreground',
          'hover:bg-accent hover:text-foreground active:bg-accent/80',
          'disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted-foreground'
        )}
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
