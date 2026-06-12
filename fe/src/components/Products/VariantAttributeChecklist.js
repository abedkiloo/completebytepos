import React, { useMemo, useState } from 'react';
import {
  clearAttributeSelection,
  mergeAttributeSelection,
  toggleAttributeSelection,
} from '../../utils/variantAttributeSelection';

function isValidHexColor(hex) {
  return typeof hex === 'string' && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex.trim());
}

/**
 * Searchable checkbox list for product variant sizes or colors.
 * Each click toggles one item — no Ctrl/Cmd needed for multi-select.
 */
export default function VariantAttributeChecklist({
  label,
  items = [],
  selectedIds = [],
  onChange,
  searchPlaceholder = 'Search…',
  getItemLabel,
  getItemSearchText,
  emptyListMessage = 'None defined yet.',
  emptySearchMessage = 'No matches.',
  'data-testid': testId,
}) {
  const [search, setSearch] = useState('');
  const selectedSet = useMemo(
    () => new Set((selectedIds || []).map(Number)),
    [selectedIds]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => getItemSearchText(item).toLowerCase().includes(q));
  }, [items, search, getItemSearchText]);

  const selectedLabels = useMemo(
    () =>
      (selectedIds || [])
        .map((id) => {
          const item = items.find((entry) => Number(entry.id) === Number(id));
          return item ? getItemLabel(item) : null;
        })
        .filter(Boolean),
    [selectedIds, items, getItemLabel]
  );

  const handleToggle = (id) => {
    onChange(toggleAttributeSelection(selectedIds, id));
  };

  const handleSelectFiltered = () => {
    onChange(mergeAttributeSelection(selectedIds, filtered.map((item) => item.id)));
  };

  const handleClear = () => {
    onChange(clearAttributeSelection());
  };

  return (
    <div
      className="form-group variant-attribute-checklist"
      data-testid={testId}
    >
      <div className="variant-attribute-checklist__heading">
        <span>{label}</span>
        <div className="variant-attribute-checklist__actions">
          <button
            type="button"
            className="text-primary underline-offset-2 hover:underline disabled:opacity-40"
            onClick={handleSelectFiltered}
            disabled={!filtered.length}
          >
            Select {search.trim() ? 'shown' : 'all'}
          </button>
          <button
            type="button"
            className="text-muted-foreground underline-offset-2 hover:underline disabled:opacity-40"
            onClick={handleClear}
            disabled={!selectedIds?.length}
          >
            Clear
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder={searchPlaceholder}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="variant-attribute-checklist__search"
        aria-label={`${label} search`}
      />

      <div
        className="variant-attribute-checklist__panel"
        role="group"
        aria-label={label}
      >
        {!items.length ? (
          <p className="text-sm text-muted-foreground">{emptyListMessage}</p>
        ) : !filtered.length ? (
          <p className="text-sm text-muted-foreground">{emptySearchMessage}</p>
        ) : (
          <div className="variant-attribute-checklist__grid">
            {filtered.map((item) => {
              const id = Number(item.id);
              const checked = selectedSet.has(id);
              const inputId = `${testId || 'variant-attr'}-${item.id}`;
              return (
                <label
                  key={item.id}
                  htmlFor={inputId}
                  className={`variant-attribute-checklist__item${
                    checked ? ' is-selected' : ''
                  }`}
                >
                  <input
                    id={inputId}
                    type="checkbox"
                    className="variant-attribute-checklist__checkbox"
                    checked={checked}
                    onChange={() => handleToggle(item.id)}
                  />
                  {isValidHexColor(item.hex_code) ? (
                    <span
                      className="variant-attribute-checklist__swatch"
                      style={{ backgroundColor: item.hex_code }}
                      aria-hidden
                    />
                  ) : null}
                  <span className="variant-attribute-checklist__label">
                    {getItemLabel(item)}
                  </span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      <small className="variant-attribute-checklist__hint">
        {selectedLabels.length
          ? `Selected (${selectedLabels.length}): ${selectedLabels.join(', ')}`
          : 'Tick each option you sell — combinations appear below with their own stock.'}
      </small>
    </div>
  );
}
