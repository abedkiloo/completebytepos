import React from 'react';
import { render, screen } from '@testing-library/react';
import CenterScreenLoader from './CenterScreenLoader';

describe('CenterScreenLoader', () => {
  it('renders nothing when closed', () => {
    render(<CenterScreenLoader open={false} label="Working…" />);
    expect(screen.queryByTestId('center-screen-loader')).not.toBeInTheDocument();
  });

  it('shows a centered status overlay with the label when open', () => {
    render(<CenterScreenLoader open label="Submitting void…" />);
    const overlay = screen.getByTestId('center-screen-loader');
    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveAttribute('role', 'status');
    expect(overlay).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('Submitting void…')).toBeInTheDocument();
  });

  it('defaults the label to Loading…', () => {
    render(<CenterScreenLoader open />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('supports a custom test id', () => {
    render(<CenterScreenLoader open testId="export-loader" label="Downloading…" />);
    expect(screen.getByTestId('export-loader')).toBeInTheDocument();
    expect(screen.queryByTestId('center-screen-loader')).not.toBeInTheDocument();
  });

  it('portals into document.body so it covers the full screen', () => {
    render(
      <div data-testid="page">
        <CenterScreenLoader open label="Please wait…" />
      </div>
    );
    const overlay = screen.getByTestId('center-screen-loader');
    expect(overlay.parentElement).toBe(document.body);
    expect(screen.getByTestId('page').contains(overlay)).toBe(false);
  });
});
