import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CartQtyInput } from './CartQtyInput';

describe('CartQtyInput', () => {
  const setup = (overrides = {}) => {
    const onDelta = jest.fn();
    const onSetQuantity = jest.fn();
    render(
      <CartQtyInput
        quantity={4}
        stockCap={10}
        onDelta={onDelta}
        onSetQuantity={onSetQuantity}
        {...overrides}
      />
    );
    return { onDelta, onSetQuantity };
  };

  test('renders current quantity in editable input', () => {
    setup();
    expect(screen.getByLabelText('Quantity')).toHaveValue('4');
  });

  test('calls onDelta when plus or minus clicked', () => {
    const { onDelta } = setup();
    fireEvent.click(screen.getByLabelText('Increase quantity'));
    fireEvent.click(screen.getByLabelText('Decrease quantity'));
    expect(onDelta).toHaveBeenCalledWith(1);
    expect(onDelta).toHaveBeenCalledWith(-1);
  });

  test('commits valid typed quantity on blur', () => {
    const { onSetQuantity } = setup();
    const input = screen.getByLabelText('Quantity');
    fireEvent.change(input, { target: { value: '7' } });
    fireEvent.blur(input);
    expect(onSetQuantity).toHaveBeenCalledWith(7);
  });

  test('shows stock error when typed quantity exceeds stock on hand', () => {
    const { onSetQuantity } = setup({ stockCap: 4 });
    const input = screen.getByLabelText('Quantity');
    fireEvent.change(input, { target: { value: '9' } });
    fireEvent.blur(input);
    expect(screen.getByRole('alert')).toHaveTextContent('Only 4 in stock on hand');
    expect(onSetQuantity).not.toHaveBeenCalled();
    expect(input).toHaveValue('4');
  });

  test('allows any quantity when stock is not tracked', () => {
    const { onSetQuantity } = setup({ stockCap: null });
    const input = screen.getByLabelText('Quantity');
    fireEvent.change(input, { target: { value: '99' } });
    fireEvent.blur(input);
    expect(onSetQuantity).toHaveBeenCalledWith(99);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
