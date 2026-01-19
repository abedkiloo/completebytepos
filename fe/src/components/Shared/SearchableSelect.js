import React, { useState, useRef, useEffect } from 'react';
import './SearchableSelect.css';

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
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      // Focus search input when dropdown opens
      if (inputRef.current && searchable) {
        setTimeout(() => inputRef.current?.focus(), 100);
      }
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, searchable]);

  // Filter options based on search term
  const filteredOptions = searchable && searchTerm
    ? options.filter(option =>
        option.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        option.label?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : options;

  const selectedOption = options.find(opt => String(opt.id || opt.value) === String(value));

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
    <div className={`searchable-select ${className}`} ref={dropdownRef}>
      <div
        className={`searchable-select-trigger ${isOpen ? 'open' : ''} ${disabled ? 'disabled' : ''}`}
        onClick={handleToggle}
      >
        <span className={selectedOption ? 'selected-value' : 'placeholder'}>
          {selectedOption ? (selectedOption.name || selectedOption.label) : placeholder}
        </span>
        <span className="dropdown-arrow">▼</span>
      </div>

      {isOpen && (
        <div className="searchable-select-dropdown">
          {searchable && (
            <div className="searchable-select-search">
              <input
                ref={inputRef}
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          )}

          <div className="searchable-select-options">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => {
                const optionValue = option.id || option.value;
                const isSelected = String(optionValue) === String(value);
                return (
                  <div
                    key={optionValue}
                    className={`searchable-select-option ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleSelect(option)}
                  >
                    {option.name || option.label}
                  </div>
                );
              })
            ) : (
              <div className="searchable-select-option no-results">
                {searchTerm ? `No results found for "${searchTerm}"` : 'No options available'}
              </div>
            )}
          </div>

          {onAddNew && (
            <div 
              className={`searchable-select-add-new ${filteredOptions.length === 0 && searchTerm ? 'highlight' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                onAddNew();
                setIsOpen(false);
                setSearchTerm('');
              }}
            >
              <span className="add-new-icon">+</span>
              <span>{addNewLabel}</span>
            </div>
          )}
        </div>
      )}

      {/* Hidden select for form compatibility */}
      <select
        name={name}
        value={value || ''}
        onChange={onChange}
        disabled={disabled}
        style={{ display: 'none' }}
      >
        <option value="">{placeholder}</option>
        {options.map(option => {
          const optionValue = option.id || option.value;
          return (
            <option key={optionValue} value={String(optionValue)}>
              {option.name || option.label}
            </option>
          );
        })}
      </select>
    </div>
  );
};

export default SearchableSelect;
