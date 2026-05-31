import React from 'react';
import { Search } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Card, CardContent } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';

export function FilterBar({ children, className }) {
  return (
    <Card className={cn('shadow-sm', className)}>
      <CardContent className="flex flex-wrap items-end gap-2 p-3">{children}</CardContent>
    </Card>
  );
}

export function FilterField({ label, children, className }) {
  return (
    <div className={cn('flex min-w-[140px] flex-1 flex-col gap-1', className)}>
      {label && (
        <label className="text-xs font-medium text-muted-foreground">{label}</label>
      )}
      {children}
    </div>
  );
}

export function SearchField({ value, onChange, placeholder = 'Search…', className }) {
  return (
    <div className={cn('relative min-w-[200px] flex-1', className)}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        type="search"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="pl-9"
      />
    </div>
  );
}

/** Segmented filter pills (All / Active / Inactive). */
export function FilterPills({ options, value, onChange }) {
  return (
    <div className="inline-flex items-center rounded-lg border bg-muted/40 p-0.5">
      {options.map((opt) => (
        <Button
          key={opt.value}
          type="button"
          variant="ghost"
          size="sm"
          className={cn(
            'h-8 rounded-md px-3 text-xs font-medium',
            value === opt.value && 'bg-background text-foreground shadow-sm'
          )}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  );
}
