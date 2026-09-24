import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import TypicalGoodsFields, {
  typicalGoodsList,
  typicalGoodsPayload,
} from './TypicalGoodsFields';

describe('TypicalGoodsFields', () => {
  test('adds and removes goods', () => {
    const onChange = jest.fn();
    const { rerender } = render(
      <TypicalGoodsFields value={['Cement']} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId('typical-good-add'));
    expect(onChange).toHaveBeenCalledWith(['Cement', '']);
    fireEvent.change(screen.getByTestId('typical-good-0'), {
      target: { value: 'Nails' },
    });
    expect(onChange).toHaveBeenCalledWith(['Nails']);
    fireEvent.click(screen.getByTestId('typical-good-remove-0'));
    expect(onChange).toHaveBeenCalledWith(['']);
    rerender(<TypicalGoodsFields value={['A', 'B']} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('typical-good-remove-0'));
    expect(onChange).toHaveBeenCalledWith(['B']);
  });

  test('payload helpers drop blanks', () => {
    expect(typicalGoodsList(null)).toEqual(['']);
    expect(typicalGoodsPayload([' Cement ', '', 'Nails'])).toEqual(['Cement', 'Nails']);
  });
});
