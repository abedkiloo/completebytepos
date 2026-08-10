import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
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
});
