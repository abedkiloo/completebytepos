import React from 'react';
import { Smartphone, Hash } from 'lucide-react';

import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { cn } from '../../lib/cn';
import {
  MPESA_RECEIPT_EXAMPLE,
  PHONE_EXAMPLE,
  mpesaReceiptMessage,
  phoneMessage,
} from '../../utils/formValidation';
import {
  MPESA_CAPTURE_CODE,
  MPESA_CAPTURE_PROMPT,
} from '../../utils/mpesaCapture';

/**
 * Interchangeable M-Pesa capture: send a PIN prompt, or type the SMS code.
 */
export default function MpesaCapture({
  mode = MPESA_CAPTURE_PROMPT,
  onModeChange,
  phone = '',
  onPhoneChange,
  code = '',
  onCodeChange,
  disabled = false,
  showErrors = false,
}) {
  const promptSelected = mode === MPESA_CAPTURE_PROMPT;
  const phoneErr = phoneMessage(phone, { required: true });
  const codeErr = mpesaReceiptMessage(code);

  return (
    <div className="space-y-2">
      <Label className="block text-xs uppercase tracking-wide text-muted-foreground">
        M-Pesa collection
      </Label>
      <div className="grid grid-cols-2 gap-1">
        <button
          type="button"
          data-testid="mpesa-capture-prompt"
          disabled={disabled}
          onClick={() => onModeChange?.(MPESA_CAPTURE_PROMPT)}
          className={cn(
            'flex items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium transition-colors',
            promptSelected
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border bg-background text-foreground hover:bg-accent'
          )}
        >
          <Smartphone className="h-4 w-4 shrink-0" />
          Prompt payment
        </button>
        <button
          type="button"
          data-testid="mpesa-capture-code"
          disabled={disabled}
          onClick={() => onModeChange?.(MPESA_CAPTURE_CODE)}
          className={cn(
            'flex items-center justify-center gap-1.5 rounded-md border px-2 py-2 text-xs font-medium transition-colors',
            !promptSelected
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border bg-background text-foreground hover:bg-accent'
          )}
        >
          <Hash className="h-4 w-4 shrink-0" />
          Add M-Pesa code
        </button>
      </div>

      {promptSelected ? (
        <div className="space-y-1">
          <Label htmlFor="mpesa-prompt-phone">Safaricom number *</Label>
          <Input
            id="mpesa-prompt-phone"
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={(e) => onPhoneChange?.(e.target.value)}
            placeholder={PHONE_EXAMPLE}
            disabled={disabled}
            aria-invalid={showErrors && Boolean(phoneErr)}
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            Sends a PIN prompt to this phone. Kenyan mobile, e.g. {PHONE_EXAMPLE}
          </p>
          {showErrors && phoneErr ? (
            <p className="text-xs text-destructive">{phoneErr}</p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-1">
          <Label htmlFor="mpesa-manual-code">M-Pesa code *</Label>
          <Input
            id="mpesa-manual-code"
            type="text"
            value={code}
            onChange={(e) => onCodeChange?.(e.target.value)}
            placeholder={MPESA_RECEIPT_EXAMPLE}
            disabled={disabled}
            aria-invalid={showErrors && Boolean(codeErr)}
            maxLength={14}
            className="font-mono"
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            At least 4 letters and numbers from the M-Pesa SMS, e.g.{' '}
            {MPESA_RECEIPT_EXAMPLE}
          </p>
          {showErrors && codeErr ? (
            <p className="text-xs text-destructive">{codeErr}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
