import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import VariantAttributeChecklist from './VariantAttributeChecklist';

const sizes = [
  { id: 1, name: 'Large', code: 'L' },
  { id: 2, name: 'Medium', code: 'M' },
];

describe('VariantAttributeChecklist', () => {
  test('toggles items without replacing the whole selection', () => {
    const onChange = jest.fn();
    render(
      <VariantAttributeChecklist
        label="Sizes"
        items={sizes}
        selectedIds={[1]}
        onChange={onChange}
        getItemLabel={(s) => s.name}
        getItemSearchText={(s) => s.name}
      />
    );

    fireEvent.click(screen.getByLabelText('Medium'));
    expect(onChange).toHaveBeenCalledWith([1, 2]);

    onChange.mockClear();
    fireEvent.click(screen.getByLabelText('Large'));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  test('filters items by search', () => {
    render(
      <VariantAttributeChecklist
        label="Sizes"
        items={sizes}
        selectedIds={[]}
        onChange={() => {}}
        getItemLabel={(s) => s.name}
        getItemSearchText={(s) => `${s.name} ${s.code}`}
      />
    );

    fireEvent.change(screen.getByLabelText('Sizes search'), { target: { value: 'med' } });
    expect(screen.getByLabelText('Medium')).toBeInTheDocument();
    expect(screen.queryByLabelText('Large')).not.toBeInTheDocument();
  });
});
