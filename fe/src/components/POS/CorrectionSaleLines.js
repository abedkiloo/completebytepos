import React from 'react';
import { FilePenLine, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { cn } from '../../lib/cn';
import { formatCurrency } from '../../utils/formatters';
import { cartVariantLabel } from '../../utils/variantCombinations';
import { CartQtyInput } from './CartQtyInput';
import { getLineStockCap } from './v2/usePOSState';
import { saleUnitPriceOverrideError } from '../../utils/saleUnitPrice';

/**
 * Editable sale lines for Correction Mode — reads as fixing a returned invoice,
 * not as a fresh cart / new sale.
 */
export default function CorrectionSaleLines({
  cart,
  itemCount,
  subtotal,
  saleNumber,
  validateStock,
  mayEditPricing,
  onUpdateQty,
  onSetQty,
  onSetLinePrice,
  onRemoveLine,
  onClearLines,
}) {
  return (
    <div
      className="flex flex-1 flex-col overflow-hidden rounded-xl border border-amber-300/80 bg-amber-50/40 shadow-sm"
      data-testid="correction-sale-lines"
    >
      <div className="flex items-center justify-between gap-2 border-b border-amber-200/80 bg-amber-100/70 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <FilePenLine className="h-4 w-4 shrink-0 text-amber-800" aria-hidden />
            <h2 className="text-sm font-semibold text-amber-950">Lines on this sale</h2>
            <Badge
              variant="secondary"
              className="border-amber-300/60 bg-white/80 text-amber-950"
            >
              {itemCount} {itemCount === 1 ? 'unit' : 'units'}
            </Badge>
          </div>
          {saleNumber ? (
            <p className="mt-0.5 truncate font-mono text-[11px] text-amber-900/80">
              {saleNumber}
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 shrink-0 text-amber-950 hover:bg-amber-200/50"
          onClick={onClearLines}
          disabled={!cart.length}
          aria-label="Remove all lines"
        >
          Clear lines
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {cart.length === 0 ? (
          <div className="px-4 py-14 text-center text-sm text-amber-900/70">
            No products on this sale yet. Use search above to add a line.
          </div>
        ) : (
          <ul className="divide-y divide-amber-200/60">
            {cart.map((item) => {
              const key = item.variant_id
                ? `${item.id}-${item.variant_id}`
                : `${item.id}`;
              const lineTotal = item.price * item.quantity;
              const stockCap = validateStock ? getLineStockCap(item) : null;
              const variant = cartVariantLabel(item);
              return (
                <li
                  key={key}
                  className="bg-white/70 px-3 py-3 sm:px-4"
                  data-testid={`correction-line-${key}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium leading-snug text-slate-900">
                        {item.name}
                      </p>
                      {variant ? (
                        <p className="mt-0.5 text-xs text-muted-foreground">{variant}</p>
                      ) : null}
                      <p className="mt-1 text-[11px] tabular-nums text-muted-foreground">
                        List {formatCurrency(item.mrp ?? item.price)}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0"
                      onClick={() => onRemoveLine(key)}
                      aria-label={`Remove ${item.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                    </Button>
                  </div>

                  <div
                    className={cn(
                      'mt-3 grid grid-cols-[1fr_auto_auto] items-end gap-2 rounded-lg border border-amber-200/70 bg-amber-50/80 p-2 sm:gap-3',
                    )}
                  >
                    <div>
                      <label
                        className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-amber-900/70"
                        htmlFor={`correction-price-${key}`}
                      >
                        Selling
                      </label>
                      <Input
                        id={`correction-price-${key}`}
                        type="number"
                        min={item.catalog_price ?? item.selling_price ?? item.price}
                        step="0.01"
                        className="h-9 bg-white px-2 text-right tabular-nums"
                        defaultValue={item.price}
                        key={`${key}-price-${item.price}`}
                        aria-label={`Unit price for ${item.name}`}
                        title="Selling price or higher"
                        onBlur={(e) => {
                          const catalog =
                            item.catalog_price ?? item.selling_price ?? item.price;
                          const error = saleUnitPriceOverrideError({
                            catalogPrice: catalog,
                            requestedPrice: e.target.value,
                            mayEditPricing,
                          });
                          if (error) {
                            e.target.value = String(item.price);
                          }
                          onSetLinePrice(key, e.target.value, { mayEditPricing });
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            e.currentTarget.blur();
                          }
                        }}
                      />
                    </div>
                    <div>
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-amber-900/70">
                        Qty
                      </span>
                      <CartQtyInput
                        quantity={item.quantity}
                        stockCap={stockCap}
                        onDelta={(delta) => onUpdateQty(key, delta)}
                        onSetQuantity={(qty) => onSetQty(key, qty)}
                        disablePlus={
                          stockCap !== null && item.quantity >= stockCap
                        }
                      />
                    </div>
                    <div className="min-w-[4.5rem] pb-1 text-right">
                      <span className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-amber-900/70">
                        Line
                      </span>
                      <p className="text-sm font-semibold tabular-nums text-slate-900">
                        {formatCurrency(lineTotal)}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {cart.length > 0 ? (
        <div className="flex items-center justify-between border-t border-amber-200/80 bg-amber-100/50 px-4 py-2.5 text-sm font-medium text-amber-950">
          <span>
            {itemCount} {itemCount === 1 ? 'unit' : 'units'} on sale
          </span>
          <span className="tabular-nums" data-testid="correction-lines-subtotal">
            {formatCurrency(subtotal)}
          </span>
        </div>
      ) : null}
    </div>
  );
}
