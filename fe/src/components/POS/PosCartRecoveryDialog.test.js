import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PosCartRecoveryDialog from './PosCartRecoveryDialog';

describe('PosCartRecoveryDialog', () => {
  it('shows message and line preview for holding recovery', () => {
    const onContinue = jest.fn();
    const onStartNew = jest.fn();

    render(
      <PosCartRecoveryDialog
        open
        source="holding"
        itemCount={3}
        label="HOLD-99"
        previewLines={[
          { name: 'Water', quantity: 2 },
          { name: 'Bread', quantity: 1 },
        ]}
        onContinue={onContinue}
        onStartNew={onStartNew}
      />
    );

    expect(screen.getByText(/Resume previous sale/i)).toBeInTheDocument();
    expect(screen.getByText(/HOLD-99/)).toBeInTheDocument();
    expect(screen.getByText('Water')).toBeInTheDocument();
    expect(screen.getByText('×2')).toBeInTheDocument();
    expect(screen.getByText('Bread')).toBeInTheDocument();
  });

  it('calls continue or start new handlers', () => {
    const onContinue = jest.fn();
    const onStartNew = jest.fn();

    render(
      <PosCartRecoveryDialog
        open
        source="local"
        itemCount={2}
        onContinue={onContinue}
        onStartNew={onStartNew}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Continue sale/i }));
    expect(onContinue).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Start new sale/i }));
    expect(onStartNew).toHaveBeenCalled();
  });

  it('renders nothing when closed or item count is zero', () => {
    const { container, rerender } = render(
      <PosCartRecoveryDialog open={false} source="local" itemCount={2} onContinue={jest.fn()} onStartNew={jest.fn()} />
    );
    expect(container).toBeEmptyDOMElement();

    rerender(
      <PosCartRecoveryDialog open source="local" itemCount={0} onContinue={jest.fn()} onStartNew={jest.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
