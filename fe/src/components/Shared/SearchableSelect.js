import React, { useState, useRef, useEffect } from 'react';
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
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
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

  const selectedOption = options.find(opt => String(opt.id || opt.value) === String(value));

  const optionKey = (option, index) => {
    const v = option.id ?? option.value;
    const base = v != null && v !== '' ? String(v) : 'option';
    return `${base}-${index}`;
  };

  const handleSelect = (option) => {
    const optionValue = option.id || option.value;
    onChange({
      target: {
        name: name,
        value: String(optionValue)
      }
    });
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  return (
    <div className={cn('relative w-full', className)} ref={dropdownRef}>
      <div
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

      {isOpen && (
        <div className="absolute left-0 right-0 top-full z-[1000] mt-1 flex max-h-[300px] flex-col overflow-hidden rounded-md border border-border bg-background shadow-lg animate-in fade-in-0 zoom-in-95">
          {searchable && (
            <div className="border-b border-border p-2">
              <input
                ref={inputRef}
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
              />
            </div>
          )}

          <div className="max-h-[200px] flex-1 overflow-y-auto">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option, index) => {
                const optionValue = option.id || option.value;
                const isSelected = String(optionValue) === String(value);
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
                {searchTerm ? `No results found for "${searchTerm}"` : 'No options available'}
              </div>
            )}
          </div>

          {onAddNew && (
            <div
              className={cn(
                'flex cursor-pointer items-center gap-2 border-t border-border bg-muted/40 px-3 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-muted',
                filteredOptions.length === 0 && searchTerm && 'border-t-2 border-t-primary bg-primary/5 font-semibold'
              )}
              onClick={(e) => {
                e.stopPropagation();
                onAddNew();
                setIsOpen(false);
                setSearchTerm('');
              }}
            >
              <span className="text-lg font-bold leading-none">+</span>
              <span>{addNewLabel}</span>
            </div>
          )}
        </div>
      )}

      <select
        name={name}
        value={value || ''}
        onChange={onChange}
        disabled={disabled}
        style={{ display: 'none' }}
      >
        <option key="__placeholder__" value="">{placeholder}</option>
        {options.map((option, index) => {
          const optionValue = option.id || option.value;
          return (
            <option key={optionKey(option, index)} value={String(optionValue)}>
              {option.name || option.label}
            </option>
          );
        })}
      </select>
    </div>
  );
};

export default SearchableSelect;
