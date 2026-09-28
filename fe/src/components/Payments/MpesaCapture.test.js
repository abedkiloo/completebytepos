import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import MpesaCapture from './MpesaCapture';
import { MPESA_CAPTURE_CODE, MPESA_CAPTURE_PROMPT } from '../../utils/mpesaCapture';
import { toast } from '../../utils/toast';

jest.mock('../../utils/toast', () => ({
  toast: { info: jest.fn(), warning: jest.fn(), error: jest.fn(), success: jest.fn() },
}));

describe('MpesaCapture', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('defaults to entering an M-Pesa code and keeps prompt as coming soon', () => {
    const onModeChange = jest.fn();
    const onCodeChange = jest.fn();

    render(
      <MpesaCapture
        mode={MPESA_CAPTURE_CODE}
        onModeChange={onModeChange}
        code=""
        onCodeChange={onCodeChange}
      />
    );

    expect(screen.getByLabelText(/M-Pesa code/i)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('mpesa-capture-prompt'));
    expect(toast.info).toHaveBeenCalledWith('Coming soon');
    expect(onModeChange).not.toHaveBeenCalled();
    expect(screen.getByTestId('mpesa-capture-prompt')).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    expect(onModeChange).toHaveBeenCalledWith(MPESA_CAPTURE_CODE);
    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: 'QHX7' },
    });
    expect(onCodeChange).toHaveBeenCalledWith('QHX7');
  });

  it('coming soon ignores forced prompt mode and keeps the M-Pesa code field', () => {
    const onPhoneChange = jest.fn();
    const onCodeChange = jest.fn();
    render(
      <MpesaCapture
        mode={MPESA_CAPTURE_PROMPT}
        phone=""
        onPhoneChange={onPhoneChange}
        code=""
        onCodeChange={onCodeChange}
        showErrors
      />
    );
    expect(screen.queryByLabelText(/Safaricom number/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/M-Pesa code/i)).toBeInTheDocument();
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: 'QHX7' },
    });
    expect(onCodeChange).toHaveBeenCalledWith('QHX7');
  });

  it('does not call mode handlers when disabled', () => {
    const onModeChange = jest.fn();
    render(
      <MpesaCapture
        mode={MPESA_CAPTURE_CODE}
        onModeChange={onModeChange}
        disabled
      />
    );
    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    fireEvent.click(screen.getByTestId('mpesa-capture-prompt'));
    expect(onModeChange).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
  });
});
