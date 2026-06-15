import React, { useEffect, useState } from 'react';
import { Minus, Plus } from 'lucide-react';

import { Button } from '../ui/button';
import { cn } from '../../lib/cn';

/**
 * Cart quantity stepper with manual numeric entry.
 * Validates against stockCap on blur / Enter and shows an inline error when over.
 */
export function CartQtyInput({
  quantity,
  stockCap = null,
  onDelta,
  onSetQuantity,
  disablePlus = false,
  className,
}) {
  const [draft, setDraft] = useState(String(quantity));
  const [stockError, setStockError] = useState('');

  useEffect(() => {
    setDraft(String(quantity));
    setStockError('');
  }, [quantity]);

  const commitDraft = () => {
    const trimmed = draft.trim();
    if (trimmed === '') {
      setDraft(String(quantity));
      setStockError('');
      return;
    }
    const parsed = parseInt(trimmed, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setDraft(String(quantity));
      setStockError('Enter a valid quantity');
      return;
    }
    if (stockCap !== null && parsed > stockCap) {
      setStockError(`Only ${stockCap} in stock on hand`);
      setDraft(String(quantity));
      return;
    }
    setStockError('');
    if (parsed !== quantity) {
      onSetQuantity(parsed);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.currentTarget.blur();
    }
  };

  return (
    <div className={cn('flex flex-col items-center gap-0.5', className)}>
      <div
        className={cn(
          'inline-flex items-center rounded-md border bg-background',
          stockError && 'border-destructive'
        )}
      >
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 rounded-none rounded-l-md"
          onClick={() => onDelta(-1)}
          aria-label="Decrease quantity"
        >
          <Minus className="h-3.5 w-3.5" />
        </Button>
        <input
          type="text"
          inputMode="numeric"
          value={draft}
          onChange={(e) => {
            setStockError('');
            setDraft(e.target.value.replace(/[^\d]/g, ''));
          }}
          onBlur={commitDraft}
          onKeyDown={handleKeyDown}
          className="h-8 w-12 border-0 bg-transparent text-center text-sm font-semibold tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
          aria-label="Quantity"
          aria-invalid={stockError ? 'true' : undefined}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 rounded-none rounded-r-md disabled:opacity-40"
          onClick={() => onDelta(1)}
          disabled={disablePlus}
          title={disablePlus ? 'No more in stock' : undefined}
          aria-label="Increase quantity"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      {stockError ? (
        <p className="max-w-[11rem] text-center text-[10px] leading-tight text-destructive" role="alert">
          {stockError}
        </p>
      ) : null}
    </div>
  );
}
