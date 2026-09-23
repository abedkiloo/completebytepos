import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import HelpHint from './HelpHint';

describe('HelpHint', () => {
  it('shows help on hover and hides on leave', () => {
    render(<HelpHint actionKey="sale_refund" />);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    const wrap = screen.getByRole('button', { name: /what is void \/ refund/i }).parentElement;
    fireEvent.mouseEnter(wrap);
    expect(screen.getByRole('tooltip')).toHaveTextContent(/customer returns/i);
    expect(screen.getByRole('tooltip')).toHaveTextContent(/Roll back/i);
    fireEvent.mouseLeave(wrap);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('toggles on click for touch and closes on escape', () => {
    render(<HelpHint actionKey="sale_rollback" side="top" />);
    const button = screen.getByRole('button', { name: /what is roll back sale/i });
    fireEvent.click(button);
    expect(screen.getByRole('tooltip')).toHaveTextContent(/should never have been recorded/i);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('accepts custom copy and closes when clicking outside', () => {
    render(
      <div>
        <HelpHint title="Custom" body="Custom body" contrast="" label="Explain custom" />
        <button type="button">Outside</button>
      </div>
    );
    fireEvent.click(screen.getByRole('button', { name: 'Explain custom' }));
    expect(screen.getByRole('tooltip')).toHaveTextContent('Custom body');
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Outside' }));
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});
