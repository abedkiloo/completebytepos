import React, { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../../lib/cn';

const SearchableSelect = ({
  value,
  onChange,
  options = [],
  placeholder = 'Select...',
  disabled = false,
  searchable = true,
  onAddNew,
  addNewLabel = '+ Add New',
  className = '',
  name = '',
  invalid = false,
  onSearchTermChange,
  noResultsHint = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [menuStyle, setMenuStyle] = useState(null);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const inputRef = useRef(null);

  const updateMenuPosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const width = Math.max(rect.width, 180);
    const viewportPad = 8;
    let left = rect.left;
    if (left + width > window.innerWidth - viewportPad) {
      left = Math.max(viewportPad, window.innerWidth - width - viewportPad);
    }
    setMenuStyle({
      position: 'fixed',
      top: rect.bottom + 4,
      left,
      width,
      zIndex: 4000,
    });
  }, []);

  useLayoutEffect(() => {
    if (!isOpen) {
      setMenuStyle(null);
      return undefined;
    }
    updateMenuPosition();
    const onReposition = () => updateMenuPosition();
    window.addEventListener('resize', onReposition);
    // Capture scroll on any ancestor so the menu stays under the trigger.
    window.addEventListener('scroll', onReposition, true);
    return () => {
      window.removeEventListener('resize', onReposition);
      window.removeEventListener('scroll', onReposition, true);
    };
  }, [isOpen, updateMenuPosition]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      const target = event.target;
      const inRoot = rootRef.current?.contains(target);
      const inMenu = menuRef.current?.contains(target);
      if (!inRoot && !inMenu) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      if (inputRef.current && searchable) {
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, searchable]);

  const filteredOptions = searchable && searchTerm
    ? options.filter(option =>
        option.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        option.label?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : options;

  const selectedOption = options.find(
    (opt) => String(opt.id ?? opt.value ?? '') === String(value ?? '')
  );

  const optionKey = (option, index) => {
    const v = option.id ?? option.value;
    const base = v != null && v !== '' ? String(v) : 'option';
    return `${base}-${index}`;
  };

  const handleSelect = (option) => {
    const optionValue = option.id ?? option.value;
    onChange({
      target: {
        name: name,
        value: optionValue == null || optionValue === '' ? '' : String(optionValue),
      },
    });
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const menu = isOpen && menuStyle
    ? createPortal(
        <div
          ref={menuRef}
          data-testid="searchable-select-menu"
          style={menuStyle}
          className="app-scroll-region flex max-h-[300px] flex-col rounded-md border border-border bg-background shadow-lg animate-in fade-in-0 zoom-in-95"
        >
          {searchable && (
            <div className="border-b border-border p-2">
              <input
                ref={inputRef}
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => {
                  const term = e.target.value;
                  setSearchTerm(term);
                  onSearchTermChange?.(term);
                }}
                onClick={(e) => e.stopPropagation()}
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
              />
            </div>
          )}

          <div className="app-scroll-region max-h-[200px] flex-1">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option, index) => {
                const optionValue = option.id ?? option.value;
                const isSelected = String(optionValue ?? '') === String(value ?? '');
                return (
                  <div
                    key={optionKey(option, index)}
                    className={cn(
                      'cursor-pointer px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted',
                      isSelected && 'bg-primary/10 font-medium text-primary'
                    )}
                    onClick={() => handleSelect(option)}
                  >
                    {option.name || option.label}
                  </div>
                );
              })
            ) : (
              <div className="cursor-default px-3 py-4 text-center text-sm text-muted-foreground">
                <p>{searchTerm ? `No results found for "${searchTerm}"` : 'No options available'}</p>
                {searchTerm && noResultsHint ? (
                  <p className="mt-2 text-left text-xs text-amber-800 dark:text-amber-200">
                    {noResultsHint}
                  </p>
                ) : null}
              </div>
            )}
          </div>

          {onAddNew && (
            <button
              type="button"
              className={cn(
                'flex w-full cursor-pointer items-center gap-2 border-t border-border bg-muted/40 px-3 py-2.5 text-left text-sm font-medium text-primary transition-colors hover:bg-muted',
                filteredOptions.length === 0 && searchTerm && 'border-t-2 border-t-primary bg-primary/5 font-semibold'
              )}
              onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onAddNew();
                setIsOpen(false);
                setSearchTerm('');
              }}
            >
              <span className="text-lg font-bold leading-none">+</span>
              <span>{addNewLabel}</span>
            </button>
          )}
        </div>,
        document.body
      )
    : null;

  return (
    <div className={cn('relative w-full', className)} ref={rootRef}>
      <div
        ref={triggerRef}
        className={cn(
          'searchable-select-trigger flex min-h-10 cursor-pointer items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors',
          isOpen && 'border-ring ring-2 ring-ring/20',
          disabled && 'cursor-not-allowed bg-muted opacity-60',
          invalid && 'border-destructive ring-2 ring-destructive/25'
        )}
        onClick={handleToggle}
      >
        <span className={cn('flex-1 text-left', selectedOption ? 'text-foreground' : 'text-muted-foreground')}>
          {selectedOption ? (selectedOption.name || selectedOption.label) : placeholder}
        </span>
        <span
          className={cn(
            'ml-2 text-xs text-muted-foreground transition-transform',
            isOpen && 'rotate-180'
          )}
          aria-hidden
        >
          ▼
        </span>
      </div>

      {menu}

      <select
        name={name}
        value={value || ''}
        onChange={onChange}
        disabled={disabled}
        style={{ display: 'none' }}
      >
        <option key="__placeholder__" value="">{placeholder}</option>
        {options.map((option, index) => {
          const optionValue = option.id ?? option.value;
          return (
            <option key={optionKey(option, index)} value={optionValue == null ? '' : String(optionValue)}>
              {option.name || option.label}
            </option>
          );
        })}
      </select>
    </div>
  );
};

export default SearchableSelect;
