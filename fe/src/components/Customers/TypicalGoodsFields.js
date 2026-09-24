import React from 'react';

export function typicalGoodsList(value) {
  if (!Array.isArray(value) || value.length === 0) return [''];
  return value;
}

export function typicalGoodsPayload(value) {
  return (Array.isArray(value) ? value : [])
    .map((item) => String(item || '').trim())
    .filter(Boolean);
}

export default function TypicalGoodsFields({
  value,
  onChange,
  idPrefix = 'typical-good',
}) {
  const items = typicalGoodsList(value);

  const setItem = (index, text) => {
    const next = [...items];
    next[index] = text;
    onChange(next);
  };

  const addItem = () => onChange([...items, '']);

  const removeItem = (index) => {
    if (items.length <= 1) {
      onChange(['']);
      return;
    }
    onChange(items.filter((_, i) => i !== index));
  };

  return (
    <div className="flex flex-col gap-2" data-testid="typical-goods-fields">
      {items.map((item, index) => (
        <div key={`${idPrefix}-${index}`} className="flex gap-2">
          <input
            id={`${idPrefix}-${index}`}
            data-testid={`${idPrefix}-${index}`}
            type="text"
            value={item}
            maxLength={80}
            onChange={(e) => setItem(index, e.target.value)}
            placeholder="e.g. Cement 50kg"
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <button
            type="button"
            className="btn btn-secondary shrink-0 px-3"
            data-testid={`${idPrefix}-remove-${index}`}
            onClick={() => removeItem(index)}
            aria-label="Remove good"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn btn-secondary self-start"
        data-testid={`${idPrefix}-add`}
        onClick={addItem}
      >
        Add another good
      </button>
    </div>
  );
}
