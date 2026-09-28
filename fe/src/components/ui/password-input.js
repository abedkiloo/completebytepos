import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

import { cn } from '../../lib/cn';
import { Input } from './input';

const PasswordInput = React.forwardRef(function PasswordInput(
  { className, disabled, ...props },
  ref
) {
  const [visible, setVisible] = useState(false);
  const label = visible ? 'Hide password' : 'Show password';

  return (
    <div className="relative">
      <Input
        ref={ref}
        type={visible ? 'text' : 'password'}
        disabled={disabled}
        className={cn('pr-10', className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((open) => !open)}
        disabled={disabled}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground focus:outline-none focus-visible:text-foreground disabled:pointer-events-none disabled:opacity-50"
        aria-label={label}
        aria-pressed={visible}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
});

PasswordInput.displayName = 'PasswordInput';

export { PasswordInput };
