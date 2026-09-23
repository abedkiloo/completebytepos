import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import MpesaCapture from './MpesaCapture';
import { MPESA_CAPTURE_CODE, MPESA_CAPTURE_PROMPT } from '../../utils/mpesaCapture';

describe('MpesaCapture', () => {
  it('shows the phone field for prompt payment and switches to code', () => {
    const onModeChange = jest.fn();
    const onPhoneChange = jest.fn();
    const onCodeChange = jest.fn();

    const { rerender } = render(
      <MpesaCapture
        mode={MPESA_CAPTURE_PROMPT}
        onModeChange={onModeChange}
        phone=""
        onPhoneChange={onPhoneChange}
        code=""
        onCodeChange={onCodeChange}
      />
    );

    expect(screen.getByLabelText(/Safaricom number/i)).toBeInTheDocument();
    expect(screen.getByText(/Sends a PIN prompt/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Safaricom number/i), {
      target: { value: '0712345678' },
    });
    expect(onPhoneChange).toHaveBeenCalledWith('0712345678');

    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    expect(onModeChange).toHaveBeenCalledWith(MPESA_CAPTURE_CODE);

    rerender(
      <MpesaCapture
        mode={MPESA_CAPTURE_CODE}
        onModeChange={onModeChange}
        phone="0712345678"
        onPhoneChange={onPhoneChange}
        code=""
        onCodeChange={onCodeChange}
        showErrors
      />
    );

    expect(screen.getByLabelText(/M-Pesa code/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Enter the M-Pesa code from the SMS \(at least 4 letters and numbers\)/i)
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/M-Pesa code/i), {
      target: { value: 'QHX7' },
    });
    expect(onCodeChange).toHaveBeenCalledWith('QHX7');

    fireEvent.click(screen.getByTestId('mpesa-capture-prompt'));
    expect(onModeChange).toHaveBeenCalledWith(MPESA_CAPTURE_PROMPT);

    rerender(
      <MpesaCapture
        mode={MPESA_CAPTURE_CODE}
        code="QHX7K2L9M1"
        showErrors
      />
    );
    expect(
      screen.queryByText(/Enter the M-Pesa code from the SMS \(at least 4 letters and numbers\)/i)
    ).not.toBeInTheDocument();
  });

  it('does not call mode handlers when disabled', () => {
    const onModeChange = jest.fn();
    render(
      <MpesaCapture
        mode={MPESA_CAPTURE_PROMPT}
        onModeChange={onModeChange}
        disabled
      />
    );
    fireEvent.click(screen.getByTestId('mpesa-capture-code'));
    expect(onModeChange).not.toHaveBeenCalled();
  });

  it('shows phone errors when asked', () => {
    render(
      <MpesaCapture
        mode={MPESA_CAPTURE_PROMPT}
        phone=""
        showErrors
      />
    );
    expect(screen.getByText(/Sends a PIN prompt/i)).toBeInTheDocument();
    expect(screen.getByText(/Enter a Kenyan mobile/i)).toBeInTheDocument();
  });
});
