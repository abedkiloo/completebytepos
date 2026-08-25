import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CommitConfirm, { CommitConfirm as NamedCommitConfirm } from './CommitConfirm';

describe('CommitConfirm', () => {
  test('renders summary rows and confirms', () => {
    const onConfirm = jest.fn();
    const onOpenChange = jest.fn();
    render(
      <NamedCommitConfirm
        open
        onOpenChange={onOpenChange}
        title="Confirm stock adjustment?"
        rows={[
          { label: 'Product', value: 'Widget' },
          { label: 'Qty', value: '+2', tone: 'success', emphasis: true },
        ]}
        onConfirm={onConfirm}
        confirmText="Confirm & adjust"
      />
    );

    expect(screen.getByText('Confirm stock adjustment?')).toBeInTheDocument();
    expect(screen.getByText('Widget')).toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /confirm & adjust/i }));
    expect(onConfirm).toHaveBeenCalled();
  });

  test('cancel closes without confirming', () => {
    const onConfirm = jest.fn();
    const onOpenChange = jest.fn();
    render(
      <CommitConfirm
        open
        onOpenChange={onOpenChange}
        title="Confirm?"
        rows={[]}
        onConfirm={onConfirm}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test('dialog close control calls onOpenChange when not submitting', () => {
    const onOpenChange = jest.fn();
    render(
      <CommitConfirm
        open
        onOpenChange={onOpenChange}
        title="Confirm?"
        rows={[{ label: 'A', value: '1' }]}
        onConfirm={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test('does not close via dialog while submitting', () => {
    const onOpenChange = jest.fn();
    render(
      <CommitConfirm
        open
        onOpenChange={onOpenChange}
        title="Confirm?"
        rows={[]}
        onConfirm={jest.fn()}
        submitting
      />
    );

    expect(screen.getByRole('button', { name: /Saving/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  test('danger variant uses destructive confirm and warning/danger tones', () => {
    render(
      <CommitConfirm
        open
        onOpenChange={jest.fn()}
        title=""
        description=""
        rows={[
          { label: 'Refund', value: '100', tone: 'danger', emphasis: true },
          { label: 'Note', value: 'Damaged', tone: 'warning' },
          { label: 'Other', value: 'x', tone: 'unknown' },
        ]}
        onConfirm={jest.fn()}
        confirmText="Confirm void"
        cancelText="Go back"
        variant="danger"
      />
    );

    expect(screen.getByText('Confirm action?')).toBeInTheDocument();
    expect(screen.queryByText(/Review the summary/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go back/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm void/i })).toBeInTheDocument();
  });

  test('warning variant and unknown variant fall back to info icon styling', () => {
    const { rerender } = render(
      <CommitConfirm
        open
        onOpenChange={jest.fn()}
        title="Warning?"
        rows={[{ label: 'Qty', value: '-1', tone: 'default' }]}
        onConfirm={jest.fn()}
        variant="warning"
      />
    );
    expect(screen.getByText('Warning?')).toBeInTheDocument();

    rerender(
      <CommitConfirm
        open
        onOpenChange={jest.fn()}
        title="Odd?"
        rows={null}
        onConfirm={jest.fn()}
        variant="mystery"
      />
    );
    expect(screen.getByText('Odd?')).toBeInTheDocument();
  });

  test('works without onOpenChange handler', () => {
    render(
      <CommitConfirm open title="No handler" onConfirm={jest.fn()} />
    );
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));
    expect(screen.getByText('No handler')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm & save/i })).toBeInTheDocument();
  });
});