import React from 'react';
import { act, render, screen, fireEvent, within } from '@testing-library/react';
import SearchableSelect from './SearchableSelect';

describe('SearchableSelect empty option values', () => {
  it('emits empty string when selecting All / blank id option', () => {
    const onChange = jest.fn();
    const { container } = render(
      <SearchableSelect
        name="status"
        value="pending"
        onChange={onChange}
        options={[
          { id: '', name: 'All Status' },
          { id: 'pending', name: 'Pending' },
        ]}
      />
    );

    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    const dropdown = container.querySelector('.absolute');
    expect(dropdown).toBeTruthy();
    fireEvent.click(within(dropdown).getByText('All Status'));

    expect(onChange).toHaveBeenCalledWith({
      target: { name: 'status', value: '' },
    });
  });

  it('calls onAddNew once when add-new is chosen', () => {
    const onAddNew = jest.fn();
    const { container } = render(
      <SearchableSelect
        name="category"
        value=""
        onChange={jest.fn()}
        options={[{ id: 1, name: 'Retail' }]}
        onAddNew={onAddNew}
        addNewLabel="+ Add category"
      />
    );

    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    fireEvent.click(screen.getByRole('button', { name: /\+ Add category/i }));
    expect(onAddNew).toHaveBeenCalledTimes(1);
  });

  it('filters by search, shows no-results hint, and closes on outside click', () => {
    const onSearchTermChange = jest.fn();
    const { container } = render(
      <SearchableSelect
        name="size"
        value=""
        onChange={jest.fn()}
        options={[
          { id: 1, name: 'Large' },
          { id: 2, label: 'Small' },
        ]}
        onSearchTermChange={onSearchTermChange}
        noResultsHint="Add a size first"
        onAddNew={jest.fn()}
      />
    );

    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    const dropdown = container.querySelector('.absolute');
    const search = screen.getByPlaceholderText('Search...');
    fireEvent.click(search);
    fireEvent.change(search, { target: { value: 'sm' } });
    expect(onSearchTermChange).toHaveBeenCalledWith('sm');
    expect(within(dropdown).getByText('Small')).toBeInTheDocument();
    expect(within(dropdown).queryByText('Large')).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: 'zzz' } });
    expect(within(dropdown).getByText('No results found for "zzz"')).toBeInTheDocument();
    expect(within(dropdown).getByText('Add a size first')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(container.querySelector('.absolute')).toBeNull();
  });

  it('does not open when disabled and lists empty options', () => {
    const { container } = render(
      <SearchableSelect
        name="empty"
        value=""
        onChange={jest.fn()}
        options={[]}
        disabled
        searchable={false}
      />
    );
    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    expect(container.querySelector('.absolute')).toBeNull();
  });

  it('selects an option by value key and ignores add-new mousedown', () => {
    const onChange = jest.fn();
    const onAddNew = jest.fn();
    const { container } = render(
      <SearchableSelect
        name="color"
        value="red"
        onChange={onChange}
        options={[{ value: 'red', label: 'Red' }, { value: 'blue', name: 'Blue' }]}
        onAddNew={onAddNew}
        invalid
      />
    );
    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    const dropdown = container.querySelector('.absolute');
    fireEvent.mouseDown(screen.getByRole('button', { name: /\+ Add New/i }));
    expect(onAddNew).not.toHaveBeenCalled();
    fireEvent.click(within(dropdown).getByText('Blue'));
    expect(onChange).toHaveBeenCalledWith({
      target: { name: 'color', value: 'blue' },
    });
  });

  it('shows an empty-state hint when there are no options', () => {
    const { container } = render(
      <SearchableSelect
        name="empty"
        value=""
        onChange={jest.fn()}
        options={[]}
        searchable={false}
      />
    );
    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    expect(screen.getByText('No options available')).toBeInTheDocument();
  });

  it('focuses search after opening', () => {
    jest.useFakeTimers();
    const { container } = render(
      <SearchableSelect
        name="size"
        value=""
        onChange={jest.fn()}
        options={[{ id: 1, name: 'Large' }]}
      />
    );
    fireEvent.click(container.querySelector('.searchable-select-trigger'));
    act(() => {
      jest.advanceTimersByTime(120);
    });
    expect(screen.getByPlaceholderText('Search...')).toHaveFocus();
    jest.useRealTimers();
  });
});
