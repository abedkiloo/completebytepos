import React from 'react';
import { Label } from '../ui/label';
import { Input } from '../ui/input';

export default function ChangeReasonField({
  value,
  onChange,
  required = true,
  hint = 'Required for price, stock, status, or delete proposals.',
  label = 'Reason for change',
  placeholder = 'e.g. Supplier price list update, cycle count correction',
}) {
  return (
    <div className="form-group rounded-md border border-amber-200 bg-amber-50/80 p-3 dark:border-amber-900 dark:bg-amber-950/30">
      <Label htmlFor="change_reason" className="text-sm font-medium">
        {label} {required ? '*' : ''}
      </Label>
      <Input
        id="change_reason"
        name="change_reason"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1.5"
        required={required}
      />
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
